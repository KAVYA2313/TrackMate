import { useEffect, useState } from "react";
import { Link, NavLink, useLocation, useNavigate } from "react-router-dom";

export default function Navbar() {
  const navigate = useNavigate();
  const location = useLocation();

  const [token, setToken] = useState(localStorage.getItem("trackmate_token"));
  const [student, setStudent] = useState(null);

  useEffect(() => {
    const savedToken = localStorage.getItem("trackmate_token");
    const savedStudent = localStorage.getItem("trackmate_student");

    setToken(savedToken);

    if (savedStudent) {
      try {
        setStudent(JSON.parse(savedStudent));
      } catch {
        setStudent(null);
      }
    } else {
      setStudent(null);
    }
  }, [location.pathname]);

  const logout = () => {
    localStorage.removeItem("trackmate_token");
    localStorage.removeItem("trackmate_student");
    localStorage.removeItem("trackmate_test");
    localStorage.removeItem("trackmate_result");
    localStorage.removeItem("trackmate_answers");
    localStorage.removeItem("trackmate_login_email");

    setToken(null);
    setStudent(null);

    navigate("/login");
  };

  const navClass = ({ isActive }) =>
    isActive ? "tm-nav-link active" : "tm-nav-link";

  return (
    <nav className="tm-navbar tm-navbar-premium">
      <div className="tm-navbar-inner">
        <Link to={token ? "/dashboard" : "/login"} className="tm-brand">
          <span className="tm-brand-icon">T</span>
          <span>TrackMate</span>
        </Link>

        <div className="tm-nav-links">
          {token ? (
            <>
              <NavLink to="/dashboard" className={navClass}>
                Dashboard
              </NavLink>

              <NavLink to="/generate-test" className={navClass}>
                Generate Test
              </NavLink>

              <NavLink to="/history" className={navClass}>
                History
              </NavLink>

              <NavLink to="/schedule" className={navClass}>
                Schedule
              </NavLink>

              <NavLink to="/coach" className={navClass}>
                AI Coach
              </NavLink>

              <span className="tm-user-pill">
                <span className="tm-user-dot"></span>
                {student?.name || "Student"}
              </span>

              <button className="tm-logout-btn" onClick={logout}>
                Logout
              </button>
            </>
          ) : (
            <>
              <NavLink to="/login" className={navClass}>
                Login
              </NavLink>

              <NavLink to="/signup" className="tm-nav-btn">
                Signup
              </NavLink>
            </>
          )}
        </div>
      </div>
    </nav>
  );
}