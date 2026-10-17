// Shared helpers for every template (docs/BACKEND.md, Templates).
//
// User text comes from data.json: plain strings, and span arrays for bullets and the summary
// ((t: text, b: bold, p: placeholder)). These helpers only place that text as content; nothing
// here evaluates it as markup or code.

// Gaps the user must fill. The same yellow as the app's placeholder token.
#let placeholder-fill = rgb("#ffe58a")

// The paper size the caller asked for: "a4" or "us-letter".
#let paper-size() = sys.inputs.at("paper", default: "a4")

// Spans as content: bold runs in strong, placeholders highlighted.
#let rich(spans) = {
  for span in spans {
    let body = [#span.t]
    if span.b { body = strong(body) }
    if span.p { body = highlight(fill: placeholder-fill, extent: 1pt, body) }
    body
  }
}

#let months = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

// "2024-03" becomes "Mar 2024"; "2024" and anything else stay as typed.
#let fmt-date(value) = {
  let value = value.trim()
  let parts = value.match(regex("^(\d{4})-(\d{1,2})$"))
  if parts != none {
    let month = int(parts.captures.at(1))
    if month >= 1 and month <= 12 {
      return months.at(month - 1) + " " + parts.captures.at(0)
    }
  }
  value
}

// "Mar 2021 – Present", "2019 – 2021", or one date when that is all there is.
#let fmt-range(dates, present: "Present") = {
  if dates == none { return "" }
  let start = fmt-date(dates.start)
  let open = dates.end == none or dates.end.trim() == ""
  if start == "" and open { return "" }
  let end = if open { present } else { fmt-date(dates.end) }
  if start == "" or start == end { end } else { start + " – " + end }
}

// Items that are not empty, joined with a separator. None when nothing is left.
#let join-items(items, sep) = items.filter(it => it != none and it != "" and it != []).join(sep)

// Email, phone, location and links of the basics, as content items.
#let contact-items(basics) = {
  let plain = (basics.email, basics.phone, basics.location).filter(it => it.trim() != "")
  plain.map(it => [#it]) + basics.links.map(it => link(it.url)[#it.label])
}

// A URL without its scheme and trailing slash, for display.
#let short-url(url) = url.replace(regex("^https?://(www\.)?"), "").trim("/", at: end)

// The item list of a section: only the list matching its kind is filled.
#let section-items(section) = section.at(section.kind)

#let has-items(section) = section-items(section).len() > 0

// Content on the left, meta such as dates or a location right-aligned.
#let split-row(lhs, rhs, gutter: 1em) = grid(
  columns: (1fr, auto),
  column-gutter: gutter,
  lhs, align(end, rhs),
)

// Previews only: with the "source-links" input, each part of the CV links to the form field it
// comes from ("cv:" and an item's id, or "cv:summary" and "cv:basics"), so a click on the preview
// can open that field. Links add no visible mark, and PDFs never set the input.
#let source-links = sys.inputs.at("source-links", default: "false") == "true"

// `body`, linked to `source`: an item with an id, or the name of a part such as "summary".
#let src(source, body) = {
  let id = if type(source) == str { source } else { source.at("id", default: none) }
  if source-links and id != none { link("cv:" + id, body) } else { body }
}

// A bullet list of rich-text bullets, skipping empty ones; nothing when none are left.
#let bullets(items, ..options) = {
  let filled = items.filter(it => it.spans.len() > 0)
  if filled.len() > 0 {
    list(..options, ..filled.map(it => src(it, rich(it.spans))))
  }
}

// Every section with items, in order, drawn by the template's own functions: one item each, and
// skills takes the section's groups. Headings and items link to their fields in previews.
#let sections(
  cv,
  section-heading: none,
  experience: none,
  project: none,
  education: none,
  skills: none,
  certification: none,
) = {
  for section in cv.sections {
    if not has-items(section) { continue }
    src(section, section-heading(section.title))
    if section.kind == "experience" {
      for item in section.experience { src(item, experience(item)) }
    } else if section.kind == "projects" {
      for item in section.projects { src(item, project(item)) }
    } else if section.kind == "education" {
      for item in section.education { src(item, education(item)) }
    } else if section.kind == "skills" {
      skills(section.skills)
    } else if section.kind == "certifications" {
      for item in section.certifications { src(item, certification(item)) }
    } else {
      bullets(section.custom)
    }
  }
}
