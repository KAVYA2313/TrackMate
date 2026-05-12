import { Link } from "react-router-dom";

export default function Home() {
  return (
    <div className="auth-shell">
      <div className="auth-hero">
        <p className="eyebrow">Smart Study Engine</p>
        <h1>Welcome to TrackMate</h1>
        <p>
          TrackMate helps students generate tests, track retention, find weak
          chapters, and build a smart study schedule.
        </p>

        <div className="auth-actions">
          <Link className="primary-btn" to="/login">
            Login
          </Link>
          <Link className="secondary-btn" to="/signup">
            Signup
          </Link>
        </div>
      </div>
    </div>
  );
}