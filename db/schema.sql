-- Esquema PostgreSQL para Supabase: Backend Tesis Apnea.
-- Ejecuta este archivo completo en Supabase: SQL Editor > New query.

CREATE TABLE IF NOT EXISTS public.usuarios (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre VARCHAR(150) NOT NULL,
    email VARCHAR(255) UNIQUE,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.resultados (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    usuario_id BIGINT REFERENCES public.usuarios(id) ON DELETE SET NULL,
    paciente_id VARCHAR(100),
    prediccion BOOLEAN NOT NULL,
    probabilidad DOUBLE PRECISION NOT NULL CHECK (probabilidad >= 0 AND probabilidad <= 1),
    clase VARCHAR(50) NOT NULL CHECK (clase IN ('apnea_central', 'sin_apnea_central')),
    modelo VARCHAR(255) NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.historial_consultas (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    usuario_id BIGINT REFERENCES public.usuarios(id) ON DELETE SET NULL,
    endpoint VARCHAR(255) NOT NULL,
    request JSONB NOT NULL DEFAULT '{}'::jsonb,
    response JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_resultados_usuario_created_at
    ON public.resultados (usuario_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_resultados_paciente_id
    ON public.resultados (paciente_id);
CREATE INDEX IF NOT EXISTS idx_historial_usuario_created_at
    ON public.historial_consultas (usuario_id, created_at DESC);

-- Usuario inicial opcional. /predict solo valida el ID si se envia usuario_id.
-- INSERT INTO public.usuarios (nombre, email) VALUES ('Administrador', 'admin@tu-dominio.com');
