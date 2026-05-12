import { Link } from "react-router-dom";

export default function Dashboard() {
  const student = getStudent();

  return (
    <main className="tm-dashboard-page">
      <section className="tm-dashboard-hero">
        <div className="tm-dashboard-hero-left">
          <span className="tm-dashboard-kicker">TrackMate MVP</span>

          <h1>
            Study smarter with tests, retention and weekly planning.
          </h1>

          <p>
            Generate chapter-wise tests, track your score, detect weak chapters,
            and follow a smart schedule based on your learning progress.
          </p>

          <div className="tm-dashboard-actions">
            <Link to="/generate-test" className="tm-dashboard-primary-btn">
              Generate Test
            </Link>

            <Link to="/schedule" className="tm-dashboard-secondary-btn">
              View Schedule
            </Link>

            <Link to="/history" className="tm-dashboard-ghost-btn">
              View History
            </Link>
          </div>
        </div>

        <div className="tm-dashboard-hero-card">
          <div className="tm-dashboard-hero-glow"></div>

          <span>Today Focus</span>
          <h2>Chapter Priority Engine</h2>

          <p>
            Low marks become revision tasks. Strong chapters unlock the next
            topic. Missed topics are shifted forward automatically.
          </p>

          <div className="tm-dashboard-hero-mini-grid">
            <div>
              <strong>70%</strong>
              <small>Study</small>
            </div>

            <div>
              <strong>30%</strong>
              <small>Revision</small>
            </div>

            <div>
              <strong>AI</strong>
              <small>Suggestion</small>
            </div>
          </div>
        </div>
      </section>

      <section className="tm-dashboard-welcome">
        <div>
          <span>Welcome back</span>
          <h2>{student?.name || "Student"}</h2>
          <p>
            Your dashboard shows the complete TrackMate flow from test to
            retention to schedule.
          </p>
        </div>

        <div className="tm-dashboard-status-pill">
          <i></i>
          System Active
        </div>
      </section>

      <section className="tm-dashboard-stat-grid">
        <InfoCard
          label="Subject"
          value="Maths"
          note="10 chapters seeded"
          icon="M"
        />

        <InfoCard
          label="Question Bank"
          value="150"
          note="Easy, Medium and Hard"
          icon="Q"
        />

        <InfoCard
          label="Flow"
          value="Test → Score"
          note="Progress and schedule update"
          icon="F"
        />

        <InfoCard
          label="Smart Plan"
          value="3 Days"
          note="Yesterday, today and tomorrow"
          icon="S"
        />
      </section>

      <section className="tm-dashboard-flow-grid">
        <FlowCard
          number="01"
          title="Generate Test"
          text="Select one or more chapters and create a random MCQ test based on difficulty."
          link="/generate-test"
          linkText="Start test"
        />

        <FlowCard
          number="02"
          title="Retention Update"
          text="After submission, chapter score, retention, weak status and priority score are updated."
          link="/history"
          linkText="View history"
        />

        <FlowCard
          number="03"
          title="Smart Schedule"
          text="Weak chapters are added back as revision and retest tasks in the daily schedule."
          link="/schedule"
          linkText="Open schedule"
        />
      </section>

      <section className="tm-dashboard-bottom-grid">
        <div className="tm-dashboard-panel">
          <div className="tm-dashboard-panel-head">
            <div>
              <span>How TrackMate works</span>
              <h2>Simple student flow</h2>
            </div>
          </div>

          <div className="tm-dashboard-steps">
            <StepItem
              title="Give chapter test"
              text="Student selects chapter and difficulty level."
            />

            <StepItem
              title="Get score analysis"
              text="System calculates marks, percentage and chapter-wise result."
            />

            <StepItem
              title="Update memory"
              text="Retention and priority score are updated using forgetting curve logic."
            />

            <StepItem
              title="Follow smart plan"
              text="Schedule engine decides what to study or revise next."
            />
          </div>
        </div>

        <div className="tm-dashboard-ai-panel">
          <span>Smart Suggestion</span>

          <h2>Focus on weak chapters first.</h2>

          <p>
            TrackMate checks your test score and retention. If your marks are
            low, revision is added automatically before new topics.
          </p>

          <Link to="/schedule">Open Smart Schedule</Link>
        </div>
      </section>
    </main>
  );
}

function getStudent() {
  try {
    const saved = localStorage.getItem("trackmate_student");
    return saved ? JSON.parse(saved) : null;
  } catch {
    return null;
  }
}

function InfoCard({ label, value, note, icon }) {
  return (
    <div className="tm-dashboard-info-card">
      <div className="tm-dashboard-card-icon">{icon}</div>

      <div>
        <span>{label}</span>
        <h3>{value}</h3>
        <p>{note}</p>
      </div>
    </div>
  );
}

function FlowCard({ number, title, text, link, linkText }) {
  return (
    <div className="tm-dashboard-flow-card">
      <div className="tm-dashboard-flow-number">{number}</div>

      <h3>{title}</h3>

      <p>{text}</p>

      <Link to={link}>{linkText} →</Link>
    </div>
  );
}

function StepItem({ title, text }) {
  return (
    <div className="tm-dashboard-step-item">
      <div className="tm-dashboard-step-dot"></div>

      <div>
        <h4>{title}</h4>
        <p>{text}</p>
      </div>
    </div>
  );
}