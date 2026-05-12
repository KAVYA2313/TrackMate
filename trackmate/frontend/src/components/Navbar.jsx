import { Link } from "react-router-dom";

export default function Navbar() {
  return (
    <nav className="nav">
      <Link to="/" className="logo">TrackMate</Link>
      <div className="links">
        <Link to="/">Dashboard</Link>
        <Link to="/generate-test">Generate Test</Link>
        <Link to="/schedule">Schedule</Link>
      </div>
    </nav>
  );
}
