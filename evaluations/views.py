from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from accounts.models import UserType
from challenges.models import Challenge, ChallengeStatus
from startups.models import Startup

from intelligence.ollama import OllamaError

from .models import (
    Application,
    ApplicationStatus,
    HumanEvaluation,
)
from .permissions import ApplicationPermission
from .serializers import (
    AIEvaluationSerializer,
    ApplicationActionSerializer,
    ApplicationSerializer,
    EligibilityResultSerializer,
    EvaluationSummarySerializer,
    HumanEvaluationSerializer,
)
from .services import (
    check_application_eligibility,
    generate_ai_evaluation,
    selection_summary,
)


class ApplicationViewSet(viewsets.ModelViewSet):
    queryset = Application.objects.select_related(
        "challenge", "startup", "startup__user", "challenge__created_by", "ai_evaluation"
    ).prefetch_related("human_evaluations")
    serializer_class = ApplicationSerializer
    permission_classes = [permissions.IsAuthenticated, ApplicationPermission]

    def get_queryset(self):
        user = self.request.user
        queryset = self.queryset
        if user.user_type == UserType.STARTUP:
            return queryset.filter(startup__user=user)
        if user.user_type == UserType.GOVERNMENT:
            # Challenge owners retain control over application state changes.
            # Any government evaluator may access applications for evaluation
            # actions so a review committee member can independently score an
            # application created by another department.
            evaluation_actions = {
                "ai_evaluate",
                "human_evaluations",
                "evaluation_summary",
            }
            if self.action in evaluation_actions:
                return queryset
            return queryset.filter(challenge__created_by=user)
        return queryset.none()

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if self.action == "create":
            challenge_id = self.request.data.get("challenge")
            if challenge_id:
                context["challenge"] = get_object_or_404(Challenge, id=challenge_id)
        return context

    def create(self, request, *args, **kwargs):
        challenge_id = request.data.get("challenge")
        if not challenge_id:
            return Response({"challenge": "This field is required."}, status=status.HTTP_400_BAD_REQUEST)
        challenge = get_object_or_404(Challenge, id=challenge_id)
        if challenge.status != ChallengeStatus.OPEN:
            return Response({"challenge": "Applications are only allowed for open challenges."}, status=status.HTTP_400_BAD_REQUEST)
        startup = get_object_or_404(Startup, user=request.user)
        serializer = self.get_serializer(data=request.data, context={**self.get_serializer_context(), "challenge": challenge})
        serializer.is_valid(raise_exception=True)
        application = serializer.save(challenge=challenge, startup=startup)
        return Response(self.get_serializer(application).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="check-eligibility")
    def check_eligibility(self, request, pk=None):
        application = self.get_object()
        if request.user.user_type != UserType.GOVERNMENT:
            return Response({"detail": "Only government users can perform eligibility checks."}, status=status.HTTP_403_FORBIDDEN)
        if application.status != ApplicationStatus.SUBMITTED:
            return Response({"detail": "Eligibility can only be checked for a submitted application."}, status=status.HTTP_400_BAD_REQUEST)
        application.transition_to(ApplicationStatus.ELIGIBILITY_CHECK)
        application.save(update_fields=["status", "updated_at"])
        try:
            application = check_application_eligibility(application)
        except DjangoValidationError as exc:
            return Response(exc.message_dict, status=status.HTTP_400_BAD_REQUEST)
        return Response(EligibilityResultSerializer({
            "eligible": application.eligibility_status,
            "reason": application.eligibility_reason,
            "status": application.status,
        }).data)

    @action(detail=True, methods=["post"], url_path="ai-evaluate")
    def ai_evaluate(self, request, pk=None):
        application = self.get_object()
        if request.user.user_type != UserType.GOVERNMENT:
            return Response({"detail": "Only government users can request AI evaluations."}, status=status.HTTP_403_FORBIDDEN)
        if application.status != ApplicationStatus.UNDER_EVALUATION:
            return Response({"detail": "AI evaluation requires an application under evaluation."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            evaluation = generate_ai_evaluation(application)
        except OllamaError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response(AIEvaluationSerializer(evaluation).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get", "post"], url_path="human-evaluations")
    def human_evaluations(self, request, pk=None):
        application = self.get_object()
        if request.user.user_type != UserType.GOVERNMENT:
            return Response({"detail": "Only government users can manage human evaluations."}, status=status.HTTP_403_FORBIDDEN)
        if application.status != ApplicationStatus.UNDER_EVALUATION:
            return Response({"detail": "Human evaluation requires an application under evaluation."}, status=status.HTTP_400_BAD_REQUEST)

        if request.method == "GET":
            evaluations = application.human_evaluations.all()
            return Response(HumanEvaluationSerializer(evaluations, many=True).data)

        serializer = HumanEvaluationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if application.human_evaluations.filter(evaluator=request.user).exists():
            return Response({"detail": "You have already evaluated this application."}, status=status.HTTP_400_BAD_REQUEST)
        evaluation = serializer.save(application=application, evaluator=request.user)
        return Response(HumanEvaluationSerializer(evaluation).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"], url_path="evaluation-summary")
    def evaluation_summary(self, request, pk=None):
        application = self.get_object()
        if request.user.user_type != UserType.GOVERNMENT:
            return Response({"detail": "Only government users can view evaluation summaries."}, status=status.HTTP_403_FORBIDDEN)
        return Response(EvaluationSummarySerializer(selection_summary(application)).data)

    @action(detail=True, methods=["post"], url_path="action")
    def action(self, request, pk=None):
        application = self.get_object()
        if request.user.user_type != UserType.GOVERNMENT:
            return Response({"detail": "Only government users can perform application actions."}, status=status.HTTP_403_FORBIDDEN)

        serializer = ApplicationActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        action_name = serializer.validated_data["action"]

        if action_name == "check_eligibility":
            return self.check_eligibility(request, pk)

        transition_map = {
            "start_evaluation": (ApplicationStatus.ELIGIBLE, ApplicationStatus.UNDER_EVALUATION),
            "select": (ApplicationStatus.UNDER_EVALUATION, ApplicationStatus.SELECTED),
            "reject": (ApplicationStatus.UNDER_EVALUATION, ApplicationStatus.REJECTED),
        }
        required_from, new_status = transition_map[action_name]
        if application.status != required_from:
            return Response({"detail": f"Action '{action_name}' requires application status {required_from}."}, status=status.HTTP_400_BAD_REQUEST)

        if action_name in {"select", "reject"} and not application.human_evaluations.exists():
            return Response({"detail": "At least one human evaluation is required before final selection or rejection."}, status=status.HTTP_400_BAD_REQUEST)

        application.transition_to(new_status)
        application.save(update_fields=["status", "updated_at"])
        return Response(self.get_serializer(application).data)

    def update(self, request, *args, **kwargs):
        application = self.get_object()
        if request.user.user_type == UserType.STARTUP:
            return Response({"detail": "Applications cannot be edited after submission."}, status=status.HTTP_400_BAD_REQUEST)
        return super().update(request, *args, **kwargs)
