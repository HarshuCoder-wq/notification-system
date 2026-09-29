import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../auth";

export default function Navbar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const onLogout = async () => {
    await logout();
    navigate("/login");
  };

  return (
    <header className="navbar">
      <Link to="/" className="brand">🔔 NotifyHub</Link>
      {user && (
        <nav>
          <Link to="/">Website</Link>
          {user.is_staff && <Link to="/admin">Notification Settings</Link>}
          <span className="muted small">{user.username}</span>
          <button className="btn ghost" onClick={onLogout}>Logout</button>
        </nav>
      )}
    </header>
  );
}
