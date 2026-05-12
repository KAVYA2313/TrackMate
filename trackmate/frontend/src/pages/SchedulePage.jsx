import { useEffect, useState } from "react";
import API from "../api/api.js";
import ScheduleCard from "../components/ScheduleCard.jsx";

export default function SchedulePage() {
  const [items, setItems] = useState([]);

  const load = async () => {
    const res = await API.get("/schedule/week/1");
    setItems(res.data);
  };

  const generate = async () => {
    await API.post("/schedule/generate", { student_id: 1, subject_id: 1, days: 7, daily_minutes: 120 });
    load();
  };

  useEffect(() => { load().catch(() => setItems([])); }, []);

  return (
    <div>
      <h1>Weekly Schedule</h1>
      <button className="btn" onClick={generate}>Generate / Refresh Schedule</button>
      <br /><br />
      <div className="grid">
        {items.map((item) => <ScheduleCard item={item} key={item.id} />)}
      </div>
    </div>
  );
}
