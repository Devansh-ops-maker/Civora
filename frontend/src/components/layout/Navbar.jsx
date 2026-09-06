import React from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import {
  Shield,
  Building2,
  Flag,
  Target,
  FileText,
  Network,
  LogOut,
  User,
  Radar,
  Sparkles,
  Landmark,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';

export default function Navbar() {
  const { user, isGovernment, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const { t, i18n } = useTranslation();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const toggleLanguage = () => {
    const nextLanguage = i18n.language === 'en' ? 'hi' : 'en';
    i18n.changeLanguage(nextLanguage);
    localStorage.setItem('civora-language', nextLanguage);
  };

  const isActive = (path) => {
    if (path === '/government' || path === '/startup') {
      return location.pathname === path;
    }
    return location.pathname.startsWith(path);
  };

  return (
    <header className="sticky top-0 z-40 w-full glass-panel border-b border-slate-200 bg-white/85 backdrop-blur-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Brand Logo */}
        <Link to="/" className="flex items-center gap-3 group">
          <div className="w-10 h-10 rounded-xl bg-slate-950 flex items-center justify-center shadow-md text-white group-hover:scale-105 transition-transform">
            <Shield className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-extrabold text-lg text-slate-900 font-display tracking-tight">
                Civora<span className="text-slate-500"></span>
              </span>
            </div>
            <p className="text-[11px] text-slate-500 font-mono">{t('platformTag')}</p>
          </div>
        </Link>

        {/* Dynamic Role Navigation Links */}
        {user ? (
          <nav className="hidden md:flex items-center gap-1 bg-slate-100/80 p-1 rounded-xl border border-slate-200">
            {isGovernment ? (
              <>
                <Link
                  to="/government"
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-bold transition ${
                    isActive('/government') && location.pathname === '/government'
                      ? 'bg-slate-950 text-white shadow-sm'
                      : 'text-slate-600 hover:text-slate-900 hover:bg-white'
                  }`}
                >
                  <Shield className="w-3.5 h-3.5" /> {t('dashboard')}
                </Link>
                <Link
                  to="/government/challenges"
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-bold transition ${
                    isActive('/government/challenges')
                      ? 'bg-slate-950 text-white shadow-sm'
                      : 'text-slate-600 hover:text-slate-900 hover:bg-white'
                  }`}
                >
                  <Flag className="w-3.5 h-3.5" /> {t('challenges')}
                </Link>
                <Link
                  to="/government/schemes"
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-bold transition ${
                    isActive('/government/schemes')
                      ? 'bg-slate-950 text-white shadow-sm'
                      : 'text-slate-600 hover:text-slate-900 hover:bg-white'
                  }`}
                >
                  <Landmark className="w-3.5 h-3.5" /> {t('govSchemes')}
                </Link>
                <Link
                  to="/government/applications"
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-bold transition ${
                    isActive('/government/applications')
                      ? 'bg-slate-950 text-white shadow-sm'
                      : 'text-slate-600 hover:text-slate-900 hover:bg-white'
                  }`}
                >
                  <FileText className="w-3.5 h-3.5" /> {t('applications')}
                </Link>
                <Link
                  to="/government/pilots"
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-bold transition ${
                    isActive('/government/pilots')
                      ? 'bg-slate-950 text-white shadow-sm'
                      : 'text-slate-600 hover:text-slate-900 hover:bg-white'
                  }`}
                >
                  <Target className="w-3.5 h-3.5" /> {t('pilots')}
                </Link>
                <Link
                  to="/government/startups"
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-bold transition ${
                    isActive('/government/startups')
                      ? 'bg-slate-950 text-white shadow-sm'
                      : 'text-slate-600 hover:text-slate-900 hover:bg-white'
                  }`}
                >
                  <Building2 className="w-3.5 h-3.5" /> {t('startupRadar')}
                </Link>
              </>
            ) : (
              <>
                <Link
                  to="/startup"
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-bold transition ${
                    isActive('/startup') && location.pathname === '/startup'
                      ? 'bg-slate-950 text-white shadow-sm'
                      : 'text-slate-600 hover:text-slate-900 hover:bg-white'
                  }`}
                >
                  <Building2 className="w-3.5 h-3.5" /> {t('dashboard')}
                </Link>
                <Link
                  to="/startup/passport"
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-bold transition ${
                    isActive('/startup/passport')
                      ? 'bg-slate-950 text-white shadow-sm'
                      : 'text-slate-600 hover:text-slate-900 hover:bg-white'
                  }`}
                >
                  <FileText className="w-3.5 h-3.5" /> {t('startupPassport')}
                </Link>
                <Link
                  to="/startup/challenges"
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-bold transition ${
                    isActive('/startup/challenges')
                      ? 'bg-slate-950 text-white shadow-sm'
                      : 'text-slate-600 hover:text-slate-900 hover:bg-white'
                  }`}
                >
                  <Flag className="w-3.5 h-3.5" /> {t('challenges')}
                </Link>
                <Link
                  to="/startup/schemes"
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-bold transition ${
                    isActive('/startup/schemes')
                      ? 'bg-slate-950 text-white shadow-sm'
                      : 'text-slate-600 hover:text-slate-900 hover:bg-white'
                  }`}
                >
                  <Landmark className="w-3.5 h-3.5" /> {t('govSchemes')}
                </Link>
                <Link
                  to="/startup/applications"
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-bold transition ${
                    isActive('/startup/applications')
                      ? 'bg-slate-950 text-white shadow-sm'
                      : 'text-slate-600 hover:text-slate-900 hover:bg-white'
                  }`}
                >
                  <FileText className="w-3.5 h-3.5" /> {t('myApplications')}
                </Link>
                <Link
                  to="/startup/pilots"
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-bold transition ${
                    isActive('/startup/pilots')
                      ? 'bg-slate-950 text-white shadow-sm'
                      : 'text-slate-600 hover:text-slate-900 hover:bg-white'
                  }`}
                >
                  <Target className="w-3.5 h-3.5" /> {t('myPilots')}
                </Link>
                <Link
                  to="/startup/trust-graph"
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-bold transition ${
                    isActive('/startup/trust-graph')
                      ? 'bg-slate-950 text-white shadow-sm'
                      : 'text-slate-600 hover:text-slate-900 hover:bg-white'
                  }`}
                >
                  <Network className="w-3.5 h-3.5" /> {t('trustGraph')}
                </Link>
              </>
            )}
          </nav>
        ) : null}

        {/* User Badge & Actions */}
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={toggleLanguage}
            className="px-2.5 py-1.5 rounded-lg border border-slate-200 bg-white text-[11px] font-bold text-slate-700 hover:text-slate-900 hover:bg-slate-100 transition"
            aria-label="Toggle language"
            title={i18n.language === 'en' ? 'Switch to Hindi' : 'Switch to English'}
          >
            {i18n.language === 'en' ? 'हिंदी' : 'EN'}
          </button>

          {user ? (
            <div className="flex items-center gap-3">
              {/* User info */}
              <div className="text-right hidden lg:block">
                <p className="text-xs font-bold text-slate-900">{user.name || user.username || user.email}</p>
                <p className="text-[10px] text-slate-500 font-mono truncate max-w-[140px]">{user.email}</p>
              </div>

              {/* Logout Button */}
              <button
                onClick={handleLogout}
                className="p-2 rounded-xl text-slate-500 hover:text-slate-900 hover:bg-slate-100 border border-slate-200 transition"
                title={t('logout')}
              >
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <Link
                to="/login"
                className="px-4 py-2 text-xs font-bold text-slate-700 hover:text-slate-900 transition"
              >
                {t('login')}
              </Link>
              <Link
                to="/register"
                className="px-4 py-2 rounded-xl text-xs font-bold bg-slate-950 text-white hover:bg-slate-800 shadow-md transition"
              >
                {t('register')}
              </Link>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
