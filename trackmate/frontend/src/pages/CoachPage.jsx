import CoachChat from "../components/CoachChat";

export default function CoachPage() {
  return (
    <div className="coach-page">
      <section className="coach-hero">
        <p className="coach-kicker">OpenAI Personal Mentor</p>
        <h1>Smart Study Coach</h1>
        <p>
          Ask what to study, why it matters, and how to improve using your current TrackMate data.
        </p>
      </section>

      <CoachChat />
    </div>
  );
}   