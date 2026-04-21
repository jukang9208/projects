-- =====================================================================
-- derived.sql
-- seoul_energy 프로젝트 파생 컬럼 / 집계 갱신
-- structured.sql 의 기본 테이블 생성 후 실행
-- =====================================================================

ALTER TABLE public.seoul_district_energy_stats
ADD COLUMN IF NOT EXISTS usage_per_person numeric(12,6),
ADD COLUMN IF NOT EXISTS usage_per_household numeric(12,6),
ADD COLUMN IF NOT EXISTS home_usage_per_household numeric(12,6);


UPDATE public.seoul_district_energy_stats
SET
  home_ratio = home_usage::numeric / NULLIF(total_usage, 0),
  public_ratio = public_usage::numeric / NULLIF(total_usage, 0),
  service_ratio = service_usage::numeric / NULLIF(total_usage, 0),
  industry_ratio = industry_usage::numeric / NULLIF(total_usage, 0),

  usage_per_person = total_usage::numeric / NULLIF(total_resident_population, 0),
  usage_per_household = total_usage::numeric / NULLIF(total_households, 0),
  home_usage_per_household = home_usage::numeric / NULLIF(total_households, 0);
