import { Link } from "react-router-dom";

export default function Dashboard() {
  return (
    <div>
      <section className="page-hero">
        <div>
          <p className="eyebrow">TrackMate MVP</p>
          <h1>Study smarter with chapter tests, retention and weekly planning.</h1>
          <p className="hero-text">
            Generate a Maths test, submit answers, calculate chapter performance and build a smart revision schedule.
          </p>
          <div className="hero-actions">
            <Link className="btn primary" to="/generate-test">Generate Test</Link>
            <Link className="btn secondary" to="/schedule">View Schedule</Link>
          </div>
        </div>
        <div className="hero-panel">
          <span className="panel-label">Today Focus</span>
          <h2>Chapter Priority Engine</h2>
          <p>Low marks → revision added. High marks → next chapter unlocked.</p>
        </div>
      </section>

      <section className="stats-grid">
        <div className="stat-card">
          <span>Subject</span>
          <strong>Maths</strong>
          <p>10 chapters seeded</p>
        </div>
        <div className="stat-card">
          <span>Question Bank</span>
          <strong>150</strong>
          <p>Easy, Medium and Hard</p>
        </div>
        <div className="stat-card">
          <span>Flow</span>
          <strong>Test → Score</strong>
          <p>Progress and schedule update</p>
        </div>
      </section>

      <section className="grid three">
        <div className="feature-card">
          <div className="icon-box">01</div>
          <h3>Generate Test</h3>
          <p>Select one or more chapters and create a random MCQ test.</p>
          <Link className="text-link" to="/generate-test">Start test →</Link>
        </div>
        <div className="feature-card">
          <div className="icon-box">02</div>
          <h3>Retention Update</h3>
          <p>After submit, chapter score is saved and progress is updated.</p>
        </div>
        <div className="feature-card">
          <div className="icon-box">03</div>
          <h3>Smart Schedule</h3>
          <p>Weak chapters are added back as revision and retest tasks.</p>
          <Link className="text-link" to="/schedule">Open schedule →</Link>
        </div>
      </section>
    </div>
  );
}
