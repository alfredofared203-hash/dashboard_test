import { Activity, CheckCircle2, CircleHelp, XCircle } from "lucide-react";
import type { WorkspaceTask } from "../types/tasksResources";

interface TaskSelectorProps {
  tasks: WorkspaceTask[];
  selectedTaskId: string | null;
  onSelect: (taskId: string) => void;
}

function healthIcon(health: WorkspaceTask["health"]) {
  if (health === "HEALTHY") return <CheckCircle2 size={13} />;
  if (health === "UNHEALTHY" || health === "CRITICAL") return <XCircle size={13} />;
  return <CircleHelp size={13} />;
}

export function TaskSelector({ tasks, selectedTaskId, onSelect }: TaskSelectorProps) {
  return (
    <section className="task-resource-panel task-selector-panel" aria-labelledby="task-selector-title">
      <header className="task-resource-panel-heading">
        <div className="task-resource-panel-title"><Activity size={15} /><h2 id="task-selector-title">Target tasks</h2></div>
        <span className="task-resource-count">{tasks.length}</span>
      </header>
      {tasks.length === 0 ? (
        <div className="task-resource-empty" role="status">
          <Activity size={22} />
          <strong>No tasks available</strong>
          <span>The backend task endpoint returned no tasks for this view.</span>
        </div>
      ) : (
        <div className="task-resource-table-wrap">
          <table className="task-resource-table">
            <thead>
              <tr>
                <th scope="col">TASK / SERVICE</th>
                <th scope="col">STATUS</th>
                <th scope="col">HEALTH</th>
                <th scope="col">AVAILABILITY</th>
              </tr>
            </thead>
            <tbody>
              {tasks.map((task) => (
                <tr key={task.id} className={selectedTaskId === task.id ? "selected" : ""}>
                  <td>
                    <button
                      className="task-resource-select"
                      type="button"
                      aria-pressed={selectedTaskId === task.id}
                      aria-label={`Inspect ${task.name}, ${task.serviceName}, ${task.status}, ${task.health}`}
                      onClick={() => onSelect(task.id)}
                    >
                      <strong>{task.name}</strong>
                      <span>{task.serviceName}</span>
                      <code>{task.taskId}</code>
                    </button>
                  </td>
                  <td><span className={`task-status-tag task-${task.status.toLowerCase()}`}>{task.status}</span></td>
                  <td><span className={`task-health-tag health-${task.health.toLowerCase()}`}>{healthIcon(task.health)}{task.health}</span></td>
                  <td><span className={`task-availability availability-${task.availability.toLowerCase().replaceAll(" ", "-")}`}>{task.availability}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <footer className="task-resource-panel-footer">LIVE RUNNING ECS TASK INVENTORY · AWS ECS</footer>
    </section>
  );
}
