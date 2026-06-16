export default function AboutArchitecturePage() {
  return (
    <>
      <h1>Production architecture</h1>
      <p className="muted">
        Overview aligned with docs/architecture/LAWAPP_PRODUCTION_GO_LIVE.md
      </p>

      <div className="card">
        <pre style={{ overflow: "auto", fontSize: "0.75rem", lineHeight: 1.4 }}>
{`Frontend (Next :3000) --> FastAPI Gateway (:8000)
        |
        +--> Admin service (:8007)
        |
        v
Case Engine Controller (orchestrator.py, brain step 11b)
        |
        v
AI Brain (19-step) + CitationGuard
        |
   +----+----+----+
   |    |    |    |
Rules RAG Graph Case/Notify
:8016 :8017 :8018 :8008/9
        |
        v
Postgres (public + knowledge.*) + Redis`}
        </pre>
      </div>

      <div className="card">
        <h2>Local health endpoints</h2>
        <ul>
          <li>
            <a href="http://localhost:8000/health">API :8000</a>
          </li>
          <li>
            <a href="http://localhost:8007/health">Admin :8007</a>
          </li>
          <li>
            <a href="http://localhost:8016/health">Rules :8016</a>
          </li>
          <li>
            <a href="http://localhost:8017/health">RAG :8017</a>
          </li>
          <li>
            <a href="http://localhost:8018/health">Graph :8018</a>
          </li>
          <li>
            <a href="http://localhost:8019/health">Redaction :8019</a>
          </li>
          <li>
            <a href="http://localhost:8020/health">Audit :8020</a>
          </li>
        </ul>
      </div>

      <p>
        <a href="http://localhost:8000/pages/architecture.html">
          Static architecture page
        </a>
      </p>
    </>
  );
}
