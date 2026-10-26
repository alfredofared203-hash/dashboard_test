from rest_framework import serializers

from apps.diagnostics.validation import SESSION_ID_PATTERN, TASK_ID_PATTERN

SAFE_FILTER_PATTERN = r"\A[^\x00-\x1f\x7f]+\Z"


class ServiceSummarySerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField()
    status = serializers.ChoiceField(
        choices=("healthy", "warning", "critical", "unknown")
    )


class TaskSummarySerializer(serializers.Serializer):
    id = serializers.CharField()
    service_id = serializers.CharField()
    name = serializers.CharField()
    status = serializers.CharField()
    health = serializers.CharField()
    desired_count = serializers.IntegerField(min_value=0, allow_null=True)
    current_count = serializers.IntegerField(min_value=0, allow_null=True)
    availability = serializers.CharField()


class ECSClusterSerializer(serializers.Serializer):
    cluster_arn = serializers.CharField()
    cluster_name = serializers.CharField()
    status = serializers.CharField()


class ECSServiceSerializer(serializers.Serializer):
    service_arn = serializers.CharField(allow_null=True)
    service_name = serializers.CharField()
    cluster_arn = serializers.CharField()
    desired_count = serializers.IntegerField(min_value=0, allow_null=True)
    running_count = serializers.IntegerField(min_value=0, allow_null=True)
    pending_count = serializers.IntegerField(min_value=0, allow_null=True)
    task_definition_arn = serializers.CharField(allow_blank=True)
    task_definition_family = serializers.CharField(allow_blank=True)
    task_definition_revision = serializers.IntegerField(allow_null=True)
    launch_type = serializers.CharField(allow_null=True)
    status = serializers.CharField(allow_null=True)


class ECSNetworkSerializer(serializers.Serializer):
    eni_id = serializers.CharField(allow_null=True)
    private_ip = serializers.IPAddressField(allow_null=True)
    subnet_id = serializers.CharField(allow_null=True)
    security_group_ids = serializers.ListField(child=serializers.CharField())


class ECSContainerSerializer(serializers.Serializer):
    container_arn = serializers.CharField(allow_null=True)
    name = serializers.CharField()
    image = serializers.CharField(allow_blank=True)
    image_digest = serializers.CharField(allow_null=True)
    last_status = serializers.CharField()
    cpu = serializers.IntegerField(allow_null=True)
    memory = serializers.IntegerField(allow_null=True)
    memory_reservation = serializers.IntegerField(allow_null=True)
    essential = serializers.BooleanField()
    runtime_id = serializers.CharField(allow_null=True)
    exit_code = serializers.IntegerField(allow_null=True)
    reason = serializers.CharField(allow_null=True)


class ECSTaskSerializer(serializers.Serializer):
    task_arn = serializers.CharField()
    task_id = serializers.CharField()
    cluster_arn = serializers.CharField()
    service_arn = serializers.CharField(allow_null=True)
    service_name = serializers.CharField(allow_null=True)
    task_definition_arn = serializers.CharField()
    task_definition_family = serializers.CharField(allow_blank=True)
    task_definition_revision = serializers.IntegerField(allow_null=True)
    desired_status = serializers.CharField()
    last_status = serializers.CharField()
    health_status = serializers.CharField()
    started_at = serializers.DateTimeField(allow_null=True)
    launch_type = serializers.CharField(allow_null=True)
    cpu = serializers.CharField(allow_null=True)
    memory = serializers.CharField(allow_null=True)
    availability_zone = serializers.CharField(allow_null=True)
    network_mode = serializers.CharField(allow_null=True)
    network = ECSNetworkSerializer()
    containers = ECSContainerSerializer(many=True)
    desired_count = serializers.IntegerField(min_value=0, allow_null=True)
    current_count = serializers.IntegerField(min_value=0, allow_null=True)


class ResourceValuesSerializer(serializers.Serializer):
    baseline = serializers.FloatField()
    current = serializers.FloatField()
    peak = serializers.FloatField()
    unit = serializers.CharField()


class ResourceImpactSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=("healthy", "warning", "critical", "unknown")
    )
    cpu_delta = serializers.FloatField()
    memory_delta = serializers.FloatField()
    network_delta = serializers.FloatField()


class TaskResourceMetricsSerializer(serializers.Serializer):
    task_id = serializers.CharField()
    cpu = ResourceValuesSerializer()
    memory = ResourceValuesSerializer()
    network = ResourceValuesSerializer()
    impact = ResourceImpactSerializer()
    source = serializers.ChoiceField(choices=("mock", "cloudwatch", "prometheus"))


class DependencyMetricSerializer(serializers.Serializer):
    current = serializers.FloatField(allow_null=True)
    peak = serializers.FloatField(allow_null=True)
    unit = serializers.CharField()
    status = serializers.ChoiceField(choices=("available", "unavailable"))


class DependencyResourceSerializer(serializers.Serializer):
    resource_id = serializers.CharField()
    resource_type = serializers.ChoiceField(choices=("rds", "elasticache"))
    resource_scope = serializers.ChoiceField(
        choices=("db_instance", "cache_cluster", "replication_group")
    )
    engine = serializers.CharField()
    status = serializers.CharField()
    availability = serializers.ChoiceField(choices=("available", "unavailable"))
    source = serializers.ChoiceField(choices=("mock", "cloudwatch"))
    metrics = serializers.DictField(child=DependencyMetricSerializer())


class DependencyListSerializer(serializers.Serializer):
    measurement_context = serializers.ChoiceField(
        choices=("active_session_observation", "current_health")
    )
    diagnostic_session_id = serializers.CharField(allow_null=True)
    resources = DependencyResourceSerializer(many=True)


class DependenciesQuerySerializer(serializers.Serializer):
    resource_type = serializers.ChoiceField(
        choices=("rds", "elasticache"),
        required=False,
    )


class LogEntrySerializer(serializers.Serializer):
    id = serializers.CharField()
    timestamp = serializers.DateTimeField()
    severity = serializers.ChoiceField(choices=("DEBUG", "INFO", "WARN", "ERROR"))
    service = serializers.CharField()
    task_id = serializers.CharField()
    source = serializers.CharField()
    message = serializers.CharField()
    diagnostic_session_id = serializers.CharField(allow_null=True)
    trace_id = serializers.CharField(allow_null=True, required=False)
    metadata = serializers.JSONField(required=False)


class LogsQuerySerializer(serializers.Serializer):
    search = serializers.RegexField(
        regex=SAFE_FILTER_PATTERN,
        required=False,
        max_length=200,
    )
    service = serializers.RegexField(
        regex=SAFE_FILTER_PATTERN,
        required=False,
        max_length=128,
    )
    task_id = serializers.RegexField(
        regex=TASK_ID_PATTERN,
        required=False,
        max_length=128,
    )
    source = serializers.RegexField(
        regex=SAFE_FILTER_PATTERN,
        required=False,
        max_length=128,
    )
    severity = serializers.ChoiceField(
        choices=("ALL", "DEBUG", "INFO", "WARN", "ERROR"),
        required=False,
    )
    since_minutes = serializers.IntegerField(required=False, min_value=5, max_value=60)
    diagnostic_session_id = serializers.RegexField(
        regex=SESSION_ID_PATTERN,
        required=False,
        max_length=36,
    )

    def validate_since_minutes(self, value: int) -> int:
        if value not in {5, 15, 30, 60}:
            raise serializers.ValidationError("Use 5, 15, 30, or 60 minutes.")
        return value


class DiagnosticImpactQuerySerializer(serializers.Serializer):
    session_id = serializers.RegexField(
        regex=SESSION_ID_PATTERN,
        required=False,
        max_length=128,
    )


class DiagnosticImpactSessionSerializer(serializers.Serializer):
    id = serializers.CharField()
    status = serializers.ChoiceField(
        choices=("running", "stopped", "completed", "failed")
    )
    target_task_id = serializers.CharField()
    started_at = serializers.DateTimeField()
    stopped_at = serializers.DateTimeField(allow_null=True)
    duration_seconds = serializers.IntegerField(min_value=0)
    error = serializers.CharField(allow_null=True)


class ImpactPhaseSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=("captured", "partial", "unavailable", "not_configured", "not_captured")
    )
    captured_at = serializers.DateTimeField(allow_null=True)
    source = serializers.ChoiceField(
        choices=("mock", "cloudwatch", "prometheus"),
        allow_null=True,
    )
    metrics = serializers.JSONField()
    sample_count = serializers.IntegerField(min_value=0)
    detail = serializers.CharField(required=False)


class ImpactDeltaSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=("available", "unavailable"))
    absolute_delta = serializers.FloatField(allow_null=True)
    percentage_delta = serializers.FloatField(allow_null=True)
    reason = serializers.CharField(allow_null=True)


class CalculatedImpactMetricSerializer(serializers.Serializer):
    unit = serializers.CharField(allow_blank=True)
    baseline = serializers.FloatField(allow_null=True)
    during = serializers.FloatField(allow_null=True)
    post = serializers.FloatField(allow_null=True)
    peak_during = serializers.FloatField(allow_null=True)
    during_delta = ImpactDeltaSerializer()
    post_delta = ImpactDeltaSerializer()


class ImpactMetricSetSerializer(serializers.Serializer):
    cpu = CalculatedImpactMetricSerializer()
    memory = CalculatedImpactMetricSerializer()
    network = CalculatedImpactMetricSerializer()


class ImpactPhasesSerializer(serializers.Serializer):
    baseline = ImpactPhaseSerializer()
    during = ImpactPhaseSerializer()
    post = ImpactPhaseSerializer()


class ImpactMeasurementsSerializer(serializers.Serializer):
    availability = serializers.ChoiceField(
        choices=("available", "partial", "unavailable")
    )
    scope = serializers.ChoiceField(
        choices=("target_task", "configured_service_aggregate")
    )
    sources = serializers.ListField(
        child=serializers.ChoiceField(
            choices=("mock", "cloudwatch", "prometheus")
        )
    )
    phases = ImpactPhasesSerializer()
    metrics = ImpactMetricSetSerializer()


class DependencyPhaseMetricSerializer(serializers.Serializer):
    current = serializers.FloatField(allow_null=True)
    peak = serializers.FloatField(allow_null=True)
    unit = serializers.CharField()
    status = serializers.ChoiceField(choices=("available", "unavailable"))


class DependencyPhaseResourceSerializer(serializers.Serializer):
    resource_id = serializers.CharField()
    resource_type = serializers.ChoiceField(choices=("rds", "elasticache"))
    resource_scope = serializers.ChoiceField(
        choices=("db_instance", "cache_cluster", "replication_group")
    )
    engine = serializers.CharField()
    status = serializers.CharField()
    availability = serializers.ChoiceField(choices=("available", "unavailable"))
    source = serializers.ChoiceField(choices=("mock", "cloudwatch"))
    metrics = serializers.DictField(child=DependencyPhaseMetricSerializer())


class DependencyPhaseSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=("captured", "empty", "unavailable", "not_configured", "not_captured")
    )
    captured_at = serializers.DateTimeField(allow_null=True)
    source = serializers.ChoiceField(
        choices=("mock", "cloudwatch"),
        allow_null=True,
    )
    resources = serializers.DictField(child=DependencyPhaseResourceSerializer())
    sample_count = serializers.IntegerField(min_value=0)
    detail = serializers.CharField(required=False)


class DependencyImpactMetricSerializer(serializers.Serializer):
    unit = serializers.CharField(allow_blank=True)
    baseline = serializers.FloatField(allow_null=True)
    during = serializers.FloatField(allow_null=True)
    post = serializers.FloatField(allow_null=True)
    peak_during = serializers.FloatField(allow_null=True)
    during_delta = ImpactDeltaSerializer()
    post_delta = ImpactDeltaSerializer()


class DependencyImpactResourceSerializer(serializers.Serializer):
    resource_id = serializers.CharField()
    resource_type = serializers.ChoiceField(choices=("rds", "elasticache"))
    resource_scope = serializers.ChoiceField(
        choices=("db_instance", "cache_cluster", "replication_group")
    )
    engine = serializers.CharField()
    status = serializers.CharField()
    metrics = serializers.DictField(child=DependencyImpactMetricSerializer())


class DependencyImpactSerializer(serializers.Serializer):
    session_id = serializers.CharField()
    availability = serializers.ChoiceField(
        choices=("available", "partial", "unavailable")
    )
    sources = serializers.ListField(
        child=serializers.ChoiceField(choices=("mock", "cloudwatch"))
    )
    phases = serializers.DictField(
        child=DependencyPhaseSerializer(),
    )
    resources = serializers.DictField(child=DependencyImpactResourceSerializer())


class DiagnosticImpactTargetSerializer(serializers.Serializer):
    task_id = serializers.CharField()
    name = serializers.CharField(allow_null=True)
    service_id = serializers.CharField(allow_null=True)
    service_name = serializers.CharField(allow_null=True)


class DiagnosticImpactSummarySerializer(serializers.Serializer):
    classification = serializers.ChoiceField(
        choices=("none", "low", "moderate", "high", "unknown")
    )
    summary = serializers.CharField()
    thresholds = serializers.DictField()


class DiagnosticImpactLogCountsSerializer(serializers.Serializer):
    session_correlated_count = serializers.IntegerField(min_value=0, allow_null=True)
    errors = serializers.IntegerField(min_value=0, allow_null=True)
    warnings = serializers.IntegerField(min_value=0, allow_null=True)
    contextual_count = serializers.IntegerField(min_value=0, allow_null=True)


class DiagnosticImpactLogsSerializer(serializers.Serializer):
    availability = serializers.ChoiceField(
        choices=("available", "unavailable", "not_configured")
    )
    session_correlated = LogEntrySerializer(many=True)
    contextual = LogEntrySerializer(many=True)
    summary = DiagnosticImpactLogCountsSerializer()


class DiagnosticImpactApiTestingSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=("not_provided",))
    message = serializers.CharField()


class DiagnosticImpactReportSerializer(serializers.Serializer):
    session = DiagnosticImpactSessionSerializer()
    target = DiagnosticImpactTargetSerializer()
    measurements = ImpactMeasurementsSerializer()
    dependencies = DependencyImpactSerializer()
    impact = DiagnosticImpactSummarySerializer()
    logs = DiagnosticImpactLogsSerializer()
    api_testing = DiagnosticImpactApiTestingSerializer()
    limitations = serializers.ListField(child=serializers.CharField())
    generated_at = serializers.DateTimeField()
