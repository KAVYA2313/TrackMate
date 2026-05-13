import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import API from "../api/api";

export default function Dashboard() {
  const student = getStudent();

  const [weakAlerts, setWeakAlerts] = useState([]);
  const [alertLoading, setAlertLoading] = useState(true);

  useEffect(() => {
    fetchWeakAlerts();
  }, []);

  const fetchWeakAlerts = async () => {
    try {
      setAlertLoading(true);

      const res = await API.get("/notifications/me");

      const rawData = res.data;

      let list = [];

      if (Array.isArray(rawData)) {
        list = rawData;
      } else if (Array.isArray(rawData?.notifications)) {
        list = rawData.notifications;
      } else if (Array.isArray(rawData?.items)) {
        list = rawData.items;
      } else if (Array.isArray(rawData?.data)) {
        list = rawData.data;
      }

      const filtered = list
        .filter((item) => {
          const type = String(item.notification_type || item.type || "").toUpperCase();
          return (
            type.includes("WEAK") ||
            item.priority_score !== undefined ||
            item.retention !== undefined ||
            item.title ||
            item.message
          );
        })
        .slice(0, 4);

      setWeakAlerts(filtered);
    } catch (err) {
      console.error("Failed to load weak topic alerts:", err);
      setWeakAlerts([]);
    } finally {
      setAlertLoading(false);
    }
  };

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
          <span>Today Focus</span>

          <h2>Chapter Priority Engine</h2>

          <p>
            Low score chapters become revision tasks. Strong chapters unlock
            the next topic. Missed topics are shifted forward automatically.
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

      <section className="tm-dashboard-weak-alerts">
        <div className="weak-alerts-head">
          <div>
            <span>AI Weak Topic Alerts</span>
            <h2>What needs attention now?</h2>
            <p>
              TrackMate checks your test performance and shows important
              revision alerts directly here.
            </p>
          </div>

          <Link to="/schedule">Open Smart Schedule</Link>
        </div>

        {alertLoading ? (
          <div className="weak-alert-loader">
            Loading AI alerts...
          </div>
        ) : weakAlerts.length === 0 ? (
          <div className="weak-alert-empty">
            <div>
              <h3>No weak topic alert right now</h3>
              <p>
                Give a chapter test. If any chapter needs revision, TrackMate
                will show the alert here.
              </p>
            </div>

            <Link to="/generate-test">Start Test</Link>
          </div>
        ) : (
          <div className="weak-alert-grid">
            {weakAlerts.map((alert, index) => (
              <WeakAlertCard key={alert.id || index} alert={alert} />
            ))}
          </div>
        )}
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
          value="600"
          note="Topic-wise Easy, Medium and Hard"
          icon="Q"
        />

        <InfoCard
          label="Flow"
          value="Test → AI"
          note="Wrong answers become topic revision"
          icon="F"
        />

        <InfoCard
          label="Smart Plan"
          value="7 Days"
          note="OpenAI weekly schedule"
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
          title="AI Weak Topic Detection"
          text="After submission, OpenAI checks wrong answers and finds the exact weak topic."
          link="/history"
          linkText="View history"
        />

        <FlowCard
          number="03"
          title="Smart Schedule"
          text="Weak topics are added into revision and retest tasks in the daily schedule."
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
              title="AI finds weak topic"
              text="OpenAI checks wrong answers and detects exact topic weakness."
            />

            <StepItem
              title="Follow smart plan"
              text="Schedule engine decides what to study or revise next."
            />
          </div>
        </div>

        <div className="tm-dashboard-ai-panel">
          <span>Smart Suggestion</span>

          <h2>Focus on weak topics first.</h2>

          <p>
            TrackMate checks your test score and weak topics. If your result
            needs improvement, revision is added before new topics.
          </p>

          <Link to="/coach">Ask AI Coach</Link>
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

function WeakAlertCard({ alert }) {
  const title =
    alert.title ||
    alert.chapter_name ||
    alert.topic_name ||
    "Revision needed";

  const message =
    alert.message ||
    alert.ai_message ||
    "This topic needs a short revision session today.";

  const retention = alert.retention;
  const priority = alert.priority_score;

  return (
    <div className="weak-alert-card">
      <div className="weak-alert-top">
        <span>AI Alert</span>
        <b>{alert.is_read ? "Seen" : "New"}</b>
      </div>

      <h3>{title}</h3>

      <p>{message}</p>

      <div className="weak-alert-meta">
        {retention !== undefined && retention !== null && (
          <span>Memory: {retention}%</span>
        )}

        {priority !== undefined && priority !== null && (
          <span>Priority: {priority}</span>
        )}
      </div>

      <div className="weak-alert-actions">
        <Link to="/schedule">Review Schedule</Link>
        <Link to="/coach">Ask AI Coach</Link>
      </div>
    </div>
  );
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