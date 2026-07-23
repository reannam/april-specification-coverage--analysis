import { Link } from "react-router-dom";
export default function NotFoundPage(){return <div className="empty-state"><strong>Page not found</strong><p>The requested workspace page does not exist.</p><Link className="button primary" to="/">Return home</Link></div>}
