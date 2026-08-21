{{/*
Expand the name of the chart.
*/}}
{{- define "ezeus.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Fully qualified app name.
*/}}
{{- define "ezeus.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{- define "ezeus.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "ezeus.labels" -}}
helm.sh/chart: {{ include "ezeus.chart" . }}
{{ include "ezeus.selectorLabels" . }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- with .Values.commonLabels }}
{{ toYaml . }}
{{- end }}
{{- end -}}

{{- define "ezeus.selectorLabels" -}}
app.kubernetes.io/name: {{ include "ezeus.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "ezeus.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
{{- default (include "ezeus.fullname" .) .Values.serviceAccount.name -}}
{{- else -}}
{{- default "default" .Values.serviceAccount.name -}}
{{- end -}}
{{- end -}}

{{- define "ezeus.imageRef" -}}
{{- $tag := default .Chart.AppVersion .Values.image.tag -}}
{{- printf "%s:%s" .Values.image.repository $tag -}}
{{- end -}}

{{- define "ezeus.postgresHost" -}}
{{- printf "%s-postgres" (include "ezeus.fullname" .) -}}
{{- end -}}

{{- define "ezeus.redisHost" -}}
{{- printf "%s-redis" (include "ezeus.fullname" .) -}}
{{- end -}}

{{- define "ezeus.ollamaHost" -}}
{{- printf "%s-ollama" (include "ezeus.fullname" .) -}}
{{- end -}}

{{- define "ezeus.redisUrl" -}}
{{- if .Values.external.redisUrl -}}
{{- .Values.external.redisUrl -}}
{{- else -}}
{{- printf "redis://%s:6379/0" (include "ezeus.redisHost" .) -}}
{{- end -}}
{{- end -}}

{{- define "ezeus.ollamaBaseUrl" -}}
{{- if .Values.external.ollamaBaseUrl -}}
{{- .Values.external.ollamaBaseUrl -}}
{{- else -}}
{{- printf "http://%s:11434" (include "ezeus.ollamaHost" .) -}}
{{- end -}}
{{- end -}}

{{- define "ezeus.secretName" -}}
{{- if .Values.existingSecret -}}
{{- .Values.existingSecret -}}
{{- else -}}
{{- printf "%s-secrets" (include "ezeus.fullname" .) -}}
{{- end -}}
{{- end -}}
