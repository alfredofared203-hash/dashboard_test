import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  Boxes,
  CheckCircle2,
  ChevronRight,
  CircleHelp,
  Container,
  Network,
  RotateCw,
  Server,
} from "lucide-react";
import { ActionButton } from "@/components/atoms/ActionButton";
import { PageTitle } from "@/components/molecules/PageTitle";
import {
  getEcsTask,
  listAllEcsTasks,
  listEcsClusters,
  listEcsServiceTasks,
  listEcsServices,
} from "@/lib/api/ecsResources";
import type { EcsCluster, EcsService, EcsTask } from "@/types/ecsResources";
import "../ecs-resources.css";

type LoadState = "loading" | "loaded" | "error";

const unavailableMessage = "ECS inventory is currently unavailable.";

function displayValue(value: string | number | null | undefined): string {
  return value === null || value === undefined || value === "" ? "Unavailable" : String(value);
}

function taskDefinition(task: EcsTask): string {
  if (!task.taskDefinitionFamily) return "Unavailable";
  return task.taskDefinitionRevision === null
    ? task.taskDefinitionFamily
    : `${task.taskDefinitionFamily}:${task.taskDefinitionRevision}`;
}

function getTaskService(task: EcsTask, services: EcsService[]): string {
  return task.serviceName
    ?? services.find((service) => service.serviceArn === task.serviceArn)?.serviceName
    ?? "Standalone task";
}

function serviceKey(service: EcsService): string {
  return service.serviceArn ?? service.serviceName;
}

function MetadataItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="ecs-metadata-item">
      <dt>{label}</dt>
      <dd>{value || "Unavailable"}</dd>
    </div>
  );
}

function InventoryLoading() {
  return (
    <section className="ecs-resource-state" role="status" aria-label="Loading ECS inventory">
      <span className="ecs-resource-spinner" />
      <strong>Loading ECS inventory</strong>
      <span>Reading configured clusters, services, and running tasks.</span>
      <div className="ecs-skeleton-grid" aria-hidden="true">
        <span /><span /><span />
      </div>
    </section>
  );
}

export function EcsResourcesPage() {
  const [clusters, setClusters] = useState<EcsCluster[]>([]);
  const [services, setServices] = useState<EcsService[]>([]);
  const [tasks, setTasks] = useState<EcsTask[]>([]);
  const [clusterArn, setClusterArn] = useState("");
  const [serviceArn, setServiceArn] = useState("");
  const [taskId, setTaskId] = useState("");
  const [taskDetails, setTaskDetails] = useState<EcsTask | null>(null);
  const [clusterState, setClusterState] = useState<LoadState>("loading");
  const [inventoryState, setInventoryState] = useState<LoadState>("loading");
  const [detailState, setDetailState] = useState<LoadState>("loaded");
  const [refreshKey, setRefreshKey] = useState(0);

  const refresh = useCallback(() => setRefreshKey((current) => current + 1), []);

  useEffect(() => {
    let active = true;
    setClusterState("loading");
    listEcsClusters().then(
      (result) => {
        if (!active) return;
        setClusters(result);
        setClusterState("loaded");
        setClusterArn((current) => (
          result.some((cluster) => cluster.clusterArn === current)
            ? current
            : result[0]?.clusterArn ?? ""
        ));
        if (result.length === 0) {
          setServices([]);
          setTasks([]);
          setServiceArn("");
          setTaskId("");
          setTaskDetails(null);
          setInventoryState("loaded");
        }
      },
      () => {
        if (!active) return;
        setClusters([]);
        setServices([]);
        setTasks([]);
        setTaskDetails(null);
        setClusterState("error");
        setInventoryState("error");
      },
    );
    return () => {
      active = false;
    };
  }, [refreshKey]);

  useEffect(() => {
    if (clusterState !== "loaded") return;
    if (!clusterArn) {
      setInventoryState("loaded");
      return;
    }
    let active = true;
    setInventoryState("loading");
    listEcsServices(clusterArn).then(
      (nextServices) => {
        if (!active) return;
        setServices(nextServices);
        setServiceArn((current) => (
          nextServices.some((service) => serviceKey(service) === current)
            ? current
            : ""
        ));
      },
      () => {
        if (!active) return;
        setServices([]);
        setTasks([]);
        setTaskDetails(null);
        setInventoryState("error");
      },
    );
    return () => {
      active = false;
    };
  }, [clusterArn, clusterState, refreshKey]);

  useEffect(() => {
    if (clusterState !== "loaded" || !clusterArn) return;
    let active = true;
    setInventoryState("loading");
    const taskRequest = serviceArn
      ? listEcsServiceTasks(clusterArn, serviceArn)
      : listAllEcsTasks().then((allTasks) => (
        allTasks.filter((task) => task.clusterArn === clusterArn)
      ));
    taskRequest.then(
      (nextTasks) => {
        if (!active) return;
        setTasks(nextTasks);
        setTaskId((current) => (
          nextTasks.some((task) => task.taskId === current) ? current : ""
        ));
        setInventoryState("loaded");
      },
      () => {
        if (!active) return;
        setTasks([]);
        setTaskDetails(null);
        setInventoryState("error");
      },
    );
    return () => {
      active = false;
    };
  }, [clusterArn, clusterState, refreshKey, serviceArn]);

  const visibleTasks = tasks;
  const selectedTask = visibleTasks.find((task) => task.taskId === taskId) ?? null;

  useEffect(() => {
    if (!clusterArn || !taskId || inventoryState !== "loaded") {
      setTaskDetails(null);
      setDetailState("loaded");
      return;
    }
    let active = true;
    setTaskDetails(null);
    setDetailState("loading");
    getEcsTask(taskId, clusterArn).then(
      (task) => {
        if (!active) return;
        setTaskDetails(task);
        setDetailState("loaded");
      },
      () => {
        if (!active) return;
        setDetailState("error");
      },
    );
    return () => {
      active = false;
    };
  }, [clusterArn, inventoryState, taskId, refreshKey]);

  const activeCluster = clusters.find((cluster) => cluster.clusterArn === clusterArn);
  const activeService = services.find((service) => serviceKey(service) === serviceArn);
  const isLoading = clusterState === "loading" || inventoryState === "loading";
  const task = taskDetails?.taskId === taskId ? taskDetails : selectedTask;

  return (
    <div className="ecs-resources-page">
      <PageTitle
        eyebrow="INFRASTRUCTURE / ECS"
        title="ECS Resources"
        description="Explore configured AWS ECS clusters, services, and currently running tasks."
        actions={(
          <ActionButton
            variant="outline"
            size="sm"
            onClick={refresh}
            disabled={isLoading}
          >
            <RotateCw size={14} /> Refresh inventory
          </ActionButton>
        )}
      />

      <section className="ecs-inventory-notice" aria-label="Inventory context">
        <span className="ecs-inventory-live"><span />LIVE ECS INVENTORY</span>
        <p>
          This workspace shows discovered infrastructure identity and configuration.
          It does not show diagnostic measurements or start diagnostic sessions.
        </p>
      </section>

      {isLoading && <InventoryLoading />}

      {!isLoading && (clusterState === "error" || inventoryState === "error") && (
        <section className="ecs-resource-state ecs-resource-state-error" role="alert">
          <AlertTriangle size={23} />
          <strong>{unavailableMessage}</strong>
          <span>Check AWS configuration and permissions.</span>
          <ActionButton variant="outline" size="sm" onClick={refresh}>
            <RotateCw size={14} /> Try again
          </ActionButton>
        </section>
      )}

      {!isLoading && clusterState === "loaded" && clusters.length === 0 && (
        <section className="ecs-resource-state" role="status">
          <Boxes size={23} />
          <strong>No ECS resources found.</strong>
          <span>No configured clusters were returned by AWS ECS.</span>
        </section>
      )}

      {!isLoading && clusterState === "loaded" && clusters.length > 0
        && inventoryState === "loaded" && (
        <>
          <section className="ecs-resource-toolbar" aria-label="ECS inventory filters">
            <label>
              <span>Cluster</span>
              <select
                value={clusterArn}
                onChange={(event) => {
                  setClusterArn(event.target.value);
                  setServiceArn("");
                  setTaskId("");
                  setTaskDetails(null);
                }}
              >
                {clusters.map((cluster) => (
                  <option value={cluster.clusterArn} key={cluster.clusterArn}>
                    {cluster.clusterName}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>Service</span>
              <select
                value={serviceArn}
                onChange={(event) => {
                  setServiceArn(event.target.value);
                  setTaskId("");
                  setTaskDetails(null);
                }}
              >
                <option value="">All services</option>
                {services.map((service) => (
                  <option value={serviceKey(service)} key={serviceKey(service)}>
                    {service.serviceName}
                  </option>
                ))}
              </select>
            </label>
            <div className="ecs-inventory-counts">
              <span><Boxes size={14} /> {clusters.length} {clusters.length === 1 ? "cluster" : "clusters"}</span>
              <span><Server size={14} /> {services.length} {services.length === 1 ? "service" : "services"}</span>
              <span><Container size={14} /> {visibleTasks.length} running {visibleTasks.length === 1 ? "task" : "tasks"}</span>
            </div>
          </section>

          <section className="ecs-resource-hierarchy" aria-label="ECS resources">
            <div className="ecs-resource-list-panel">
              <header className="ecs-panel-heading">
                <div>
                  <h2>Running tasks</h2>
                  <p>{activeCluster?.clusterName ?? "Selected cluster"}{activeService ? ` / ${activeService.serviceName}` : ""}</p>
                </div>
                <span className="ecs-live-count">{visibleTasks.length}</span>
              </header>
              {visibleTasks.length === 0 ? (
                <div className="ecs-task-list-empty" role="status">
                  <CircleHelp size={19} />
                  <strong>No ECS resources found.</strong>
                  <span>No currently running tasks were returned for this selection.</span>
                </div>
              ) : (
                <ul className="ecs-task-list">
                  {visibleTasks.map((item) => (
                    <li key={item.taskId}>
                      <button
                        type="button"
                        className={`ecs-task-option ${taskId === item.taskId ? "selected" : ""}`}
                        onClick={() => setTaskId(item.taskId)}
                        aria-pressed={taskId === item.taskId}
                      >
                        <span className="ecs-task-option-icon"><Container size={16} /></span>
                        <span className="ecs-task-option-copy">
                          <strong>{item.taskId}</strong>
                          <small>{getTaskService(item, services)} · {taskDefinition(item)}</small>
                        </span>
                        <span className="ecs-task-status">{item.lastStatus}</span>
                        <ChevronRight size={15} className="ecs-task-chevron" />
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="ecs-resource-detail-panel">
              {!task && (
                <div className="ecs-task-detail-empty" role="status">
                  <Network size={23} />
                  <strong>Select a running task</strong>
                  <span>Choose a task to inspect its safe ECS metadata.</span>
                </div>
              )}

              {task && detailState === "loading" && (
                <div className="ecs-task-detail-empty" role="status">
                  <span className="ecs-resource-spinner" />
                  <strong>Loading task details</strong>
                </div>
              )}

              {task && detailState === "error" && (
                <div className="ecs-task-detail-error" role="alert">
                  <AlertTriangle size={19} />
                  <strong>{unavailableMessage}</strong>
                  <span>Task metadata could not be refreshed. Try refreshing the inventory.</span>
                </div>
              )}

              {task && detailState === "loaded" && (
                <>
                  <header className="ecs-task-detail-heading">
                    <span className="ecs-task-detail-icon"><Container size={18} /></span>
                    <div>
                      <span>SELECTED ECS TASK</span>
                      <h2>{task.taskId}</h2>
                    </div>
                    <span className="ecs-task-state"><CheckCircle2 size={13} /> {task.lastStatus}</span>
                  </header>
                  <dl className="ecs-metadata-grid">
                    <MetadataItem label="Cluster" value={displayValue(activeCluster?.clusterName)} />
                    <MetadataItem label="Service" value={getTaskService(task, services)} />
                    <MetadataItem label="Task ID" value={task.taskId} />
                    <MetadataItem label="Task ARN" value={task.taskArn} />
                    <MetadataItem label="Task Definition" value={taskDefinition(task)} />
                    <MetadataItem label="Task Status" value={task.lastStatus} />
                    <MetadataItem
                      label="Containers"
                      value={task.containers.length
                        ? task.containers.map((container) => `${container.name} (${container.lastStatus})`).join(", ")
                        : "Unavailable"}
                    />
                    <MetadataItem label="Private IP" value={displayValue(task.network.privateIp)} />
                    <MetadataItem label="ENI" value={displayValue(task.network.eniId)} />
                    <MetadataItem label="Subnet" value={displayValue(task.network.subnetId)} />
                    <MetadataItem
                      label="Security Groups"
                      value={task.network.securityGroupIds.length
                        ? task.network.securityGroupIds.join(", ")
                        : "Unavailable"}
                    />
                    <MetadataItem label="Network Mode" value={displayValue(task.networkMode)} />
                    <MetadataItem label="Availability Zone" value={displayValue(task.availabilityZone)} />
                  </dl>
                  <section className="ecs-diagnostic-note">
                    <CheckCircle2 size={15} />
                    <p>
                      This live task identity can be selected later as a diagnostic target
                      through the existing diagnostic workflow. Diagnostic measurements are
                      shown separately in Tasks &amp; Resources Testing.
                    </p>
                  </section>
                </>
              )}
            </div>
          </section>
        </>
      )}
    </div>
  );
}
