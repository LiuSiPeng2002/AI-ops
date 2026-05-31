{{- define "aiops.fullname" -}}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "aiops.backend.name" -}}
{{- printf "%s-backend" (include "aiops.fullname" .) }}
{{- end }}

{{- define "aiops.frontend.name" -}}
{{- printf "%s-frontend" (include "aiops.fullname" .) }}
{{- end }}

{{- define "aiops.mysql.name" -}}
{{- printf "%s-mysql" (include "aiops.fullname" .) }}
{{- end }}

{{- define "aiops.ollama.name" -}}
{{- printf "%s-ollama" (include "aiops.fullname" .) }}
{{- end }}
