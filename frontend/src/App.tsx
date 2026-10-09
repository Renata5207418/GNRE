import {
  CircleUserRound,
  FileSpreadsheet,
  Files,
  LayoutDashboard,
  ShieldCheck,
} from "lucide-react";

import {
  Navigate,
  NavLink,
  Outlet,
  Route,
  Routes,
  useLocation,
} from "react-router-dom";

import { useAuth } from "./contexts/AuthContext";

import DashboardPage from "./pages/DashboardPage";
import GuiasPage from "./pages/GuiasPage";
import ImportarPlanilhaGNRE from "./components/ImportarPlanilhaGNRE";

import CertificadosPage from "./pages/CertificadosPage";
import LoginPage from "./pages/LoginPage";
import CadastroPage from "./pages/CadastroPage";
import RecuperarSenhaPage from "./pages/RecuperarSenhaPage";
import RedefinirSenhaPage from "./pages/RedefinirSenhaPage";
import ContaPage from "./pages/ContaPage";


const menu = [
  {
    rota: "/dashboard",
    nome: "Visão geral",
    icon: LayoutDashboard,
  },
  {
    rota: "/importar",
    nome: "Importar planilha",
    icon: FileSpreadsheet,
  },
  {
    rota: "/guias",
    nome: "Acompanhamento",
    icon: Files,
  },
  {
    rota: "/certificados",
    nome: "Certificados digitais",
    icon: ShieldCheck,
  },
  {
    rota: "/conta",
    nome: "Minha conta",
    icon: CircleUserRound,
  },
];


function VerificandoSessao() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-gnre-bg">
      <div
        role="status"
        className="rounded-xl bg-white px-6 py-4 text-sm text-gnre-green shadow-sm"
      >
        Verificando sua sessão...
      </div>
    </div>
  );
}


function ExigirLogin() {
  const { usuario, carregando } = useAuth();
  const local = useLocation();

  if (carregando) {
    return <VerificandoSessao />;
  }

  if (!usuario) {
    return (
      <Navigate
        to="/login"
        replace
        state={{
          from: `${local.pathname}${local.search}`,
        }}
      />
    );
  }

  return <Outlet />;
}


function LayoutInterno() {
  const local = useLocation();
  const { usuario } = useAuth();

  const pagina = menu.find(
    (item) => item.rota === local.pathname
  );

  return (
    <div className="min-h-screen bg-gnre-bg lg:flex">
      <aside className="bg-gnre-green text-white lg:fixed lg:inset-y-0 lg:w-64">
        <div className="px-5 pb-7 pt-6">
          <div className="flex items-center justify-center rounded-2xl bg-white/60 px-4 py-2 shadow-sm">
            <img
              src="/gnre.png"
              alt="GNRE"
              className="h-[70px] w-full object-contain"
            />
          </div>
        </div>

        <div className="px-6 pb-3 text-[11px] font-semibold uppercase tracking-widest text-white/50">
          Menu principal
        </div>

        <nav
          aria-label="Menu principal"
          className="flex gap-1 overflow-x-auto px-3 pb-4 lg:flex-col lg:overflow-visible"
        >
          {menu.map((item) => {
            const Icone = item.icon;

            return (
              <NavLink
                key={item.rota}
                to={item.rota}
                className={({ isActive }) =>
                  [
                    "flex shrink-0 items-center gap-3 rounded-xl px-4 py-3 text-sm font-medium",
                    isActive
                      ? "bg-white text-gnre-green shadow-sm"
                      : "text-white/75 hover:bg-white/10 hover:text-white",
                  ].join(" ")
                }
              >
                <Icone size={18} />
                {item.nome}
              </NavLink>
            );
          })}
        </nav>

        <div className="hidden lg:absolute lg:bottom-6 lg:left-6">
          <p className="text-xs text-white/45">
            GNRE • Sistema interno
          </p>
        </div>
      </aside>

      <div className="min-w-0 flex-1 lg:ml-64">
        <header className="flex min-h-20 items-center justify-between gap-3 border-b border-[#E5E7E2] bg-white px-5 md:px-9">
          <div>
            <p className="text-xs text-gray-400">
              Sistema GNRE
            </p>

            <h1 className="text-lg font-semibold text-gnre-text">
              {pagina?.nome ?? "GNRE"}
            </h1>
          </div>

          <NavLink
            to="/conta"
            title="Minha conta"
            className="flex items-center gap-2 rounded-xl bg-gnre-bg px-3 py-2 text-gnre-green hover:bg-[#E7F0F3]"
          >
            <CircleUserRound size={22} />

            <span className="hidden max-w-40 truncate text-sm font-medium sm:block">
              {usuario?.nome}
            </span>
          </NavLink>
        </header>

        <main className="mx-auto max-w-7xl p-5 md:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}


export default function App() {
  const { carregando } = useAuth();

  if (carregando) {
    return <VerificandoSessao />;
  }

  return (
    <Routes>
      <Route
        path="/login"
        element={<LoginPage />}
      />

      <Route
        path="/cadastro"
        element={<CadastroPage />}
      />

      <Route
        path="/recuperar-senha"
        element={<RecuperarSenhaPage />}
      />

      <Route
        path="/redefinir-senha"
        element={<RedefinirSenhaPage />}
      />

      <Route element={<ExigirLogin />}>
        <Route element={<LayoutInterno />}>
          <Route
            path="/dashboard"
            element={<DashboardPage />}
          />

          <Route
            path="/importar"
            element={<ImportarPlanilhaGNRE />}
          />

          <Route
            path="/guias"
            element={<GuiasPage />}
          />

          <Route
            path="/certificados"
            element={<CertificadosPage />}
          />

          <Route
            path="/conta"
            element={<ContaPage />}
          />
        </Route>
      </Route>

      <Route
        path="*"
        element={<Navigate to="/dashboard" replace />}
      />
    </Routes>
  );
}
