from django.db import migrations
from pgvector.django import HnswIndex, VectorField
from django.conf import settings


class Migration(migrations.Migration):
    dependencies = [
        ("challenges", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="challenge",
            name="embedding",
            field=VectorField(blank=True, dimensions=settings.EMBEDDING_DIMENSIONS, null=True),
        ),
        migrations.AddIndex(
            model_name="challenge",
            index=HnswIndex(
                name="challenge_embedding_hnsw",
                fields=["embedding"],
                m=16,
                ef_construction=64,
                opclasses=["vector_cosine_ops"],
            ),
        ),
    ]
