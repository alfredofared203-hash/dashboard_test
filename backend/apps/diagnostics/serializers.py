from rest_framework import serializers

from apps.diagnostics.validation import SESSION_ID_PATTERN, TASK_ID_PATTERN


class CreateDiagnosticSessionSerializer(serializers.Serializer):
    target_task_id = serializers.RegexField(
        regex=TASK_ID_PATTERN,
        max_length=128,
    )

    def to_internal_value(self, data):
        if isinstance(data, dict):
            unexpected = set(data).difference(self.fields)
            if unexpected:
                raise serializers.ValidationError({
                    field: "This field is not supported."
                    for field in sorted(unexpected)
                })
        return super().to_internal_value(data)


class DiagnosticExecutionSerializer(serializers.Serializer):
    provider = serializers.ChoiceField(choices=("inmemory", "ecs"))
    status = serializers.ChoiceField(
        choices=("running", "stopped", "completed", "failed")
    )


class DiagnosticSessionSerializer(serializers.Serializer):
    id = serializers.CharField()
    status = serializers.ChoiceField(
        choices=("running", "stopped", "completed", "failed")
    )
    target_task_id = serializers.CharField()
    started_at = serializers.DateTimeField()
    stopped_at = serializers.DateTimeField(allow_null=True)
    duration_seconds = serializers.IntegerField(min_value=0)
    execution = DiagnosticExecutionSerializer(allow_null=True)
    error = serializers.CharField(allow_null=True)
