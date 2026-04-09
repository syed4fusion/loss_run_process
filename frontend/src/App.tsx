import { Navigate, Route, Routes } from "react-router-dom";
import UploadPage from "./pages/UploadPage";
import LoadingPage from "./pages/LoadingPage";
import ReviewPage from "./pages/ReviewPage";
import DocumentsPage from "./pages/DocumentsPage";
import ResultPage from "./pages/ResultPage";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<UploadPage />} />
      <Route path="/jobs/:id/loading" element={<LoadingPage />} />
      <Route path="/jobs/:id/review" element={<ReviewPage />} />
      <Route path="/jobs/:id/documents" element={<DocumentsPage />} />
      <Route path="/jobs/:id/result" element={<ResultPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
