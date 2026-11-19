import { Link } from "react-router-dom";
import { Button, EmptyState } from "../components/ui";

export default function NotFound() {
  return (
    <EmptyState title="This page does not exist" action={<Link to="/dashboard"><Button size="sm">Go to overview</Button></Link>}>
      Check the address, or use the navigation to open a workflow.
    </EmptyState>
  );
}
