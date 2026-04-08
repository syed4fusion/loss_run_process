import { Navigate, Route, Routes } from "react-router-dom";
import NewJobPage from "./pages/NewJobPage";
import JobStatusPage from "./pages/JobStatusPage";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<NewJobPage />} />
      <Route path="/jobs/:id" element={<JobStatusPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
