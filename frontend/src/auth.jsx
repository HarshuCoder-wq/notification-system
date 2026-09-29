import { createContext, useContext, useEffect, useState } from "react";
import api from "./api";
import { linkUser, unlinkUser } from "./push";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(Boolean(localStorage.getItem("access")));

  useEffect(() => {
    if (!localStorage.getItem("access")) return;
    api
      .get("/auth/me/")
      .then((r) => {
        setUser(r.data);
        linkUser(r.data.id);
      })
      .catch(() => localStorage.removeItem("access"))
      .finally(() => setLoading(false));
  }, []);

  const saveSession = (data) => {
    localStorage.setItem("access", data.access);
    setUser(data.user);
    linkUser(data.user.id);
    return data.user;
  };

  const login = async (username, password) => saveSession((await api.post("/auth/login/", { username, password })).data);
  const register = async (payload) => saveSession((await api.post("/auth/register/", payload)).data);

  const logout = async () => {
    try {
      await api.post("/auth/logout/"); // fires the "logout" trigger on the backend
    } finally {
      localStorage.removeItem("access");
      setUser(null);
      unlinkUser();
    }
  };

  return (
    <AuthContext.Provider value={{ user, setUser, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
