// CV and API types, generated from the api's OpenAPI schema (bun run gen:api). Never hand-written.
import type { Schemas } from '#lib/api/client.ts';

export type CvContent = Schemas['CvContent-Output'];
export type Basics = Schemas['Basics-Output'];
export type Link = Schemas['Link'];
export type Section = Schemas['Section-Output'];
export type SectionKind = Section['kind'];
export type ExperienceItem = Schemas['ExperienceItem-Output'];
export type Engagement = Schemas['Engagement-Output'];
export type ProjectItem = Schemas['ProjectItem-Output'];
export type EducationItem = Schemas['EducationItem-Output'];
export type SkillGroup = Schemas['SkillGroup'];
export type CertificationItem = Schemas['CertificationItem-Output'];
export type Bullet = Schemas['Bullet-Output'];
export type DateRange = Schemas['DateRange-Output'];

export type Profile = Schemas['Profile'];
export type ProfileSummary = Schemas['ProfileSummary'];
export type CvDocument = Schemas['Document'];
export type DocumentSummary = Schemas['DocumentSummary'];
export type Version = Schemas['Version'];
export type TemplateMeta = Schemas['TemplateMeta'];
export type SvgPages = Schemas['SvgPages'];

/** One Typst diagnostic, as the preview endpoint returns it in error details. */
export interface Diagnostic {
	message: string;
	line?: number | null;
	column?: number | null;
	file?: string | null;
}

/** A placeholder left in a CV, as the export endpoint lists it when it refuses. */
export interface PlaceholderRef {
	text: string;
	bullet_id?: string | null;
}
