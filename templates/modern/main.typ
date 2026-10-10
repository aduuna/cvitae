// Modern: Geist sans serif, left-aligned header with a two-column block (name and headline,
// contact details), single-column body with small uppercase section labels.
#import "/_lib/cv.typ": *
#let cv = json("data.json")

#let ink = rgb("#18181b")
#let accent = rgb("#2563eb")
#let muted = rgb("#5f6670")
#let rule = rgb("#d9dce1")

#set document(title: cv.basics.name + " CV", author: cv.basics.name)
#set page(paper: paper-size(), margin: (x: 1.6cm, y: 1.4cm))
#set text(font: "Geist", size: 9.5pt, fill: ink, lang: "en", hyphenate: false)
#set par(leading: 0.55em, spacing: 0.7em)
#set list(marker: text(fill: accent)[•], indent: 0.1em, body-indent: 0.5em, spacing: 0.45em)
#show link: set text(fill: ink)

#let meta(body) = text(fill: muted, body)

#let section-heading(title) = block(above: 1.15em, below: 0.6em, sticky: true)[
  #text(size: 8.5pt, weight: "semibold", fill: accent, tracking: 0.08em, upper(title))
  #v(-0.55em)
  #line(length: 100%, stroke: 0.5pt + rule)
]

#let engagement(item) = pad(left: 0.9em, top: 0.1em)[
  #let label = if item.label.trim() != "" { meta[#item.label · ] }
  #split-row(
    [#label#text(weight: "medium", item.name)],
    meta(join-items((item.location, fmt-range(item.dates)), [ · ])),
  )
  #v(-0.2em)
  #bullets(item.bullets)
]

#let experience(item) = block(below: 0.95em)[
  #split-row(
    [#text(weight: "semibold", item.role) #meta[at] #text(weight: "medium", item.org)],
    meta(fmt-range(item.dates)),
  )
  #let details = join-items((item.location, item.stack.join(", ")), [ · ])
  #if details != none {
    v(-0.35em)
    text(size: 8.5pt, fill: muted, details)
  }
  #v(-0.15em)
  #bullets(item.bullets)
  #for engagement-item in item.engagements { engagement(engagement-item) }
]

#let project(item) = block(below: 0.85em)[
  #let details = join-items(
    (item.status, if item.url != none { link(item.url, short-url(item.url)) }),
    [ · ],
  )
  #split-row(
    [#text(weight: "semibold", item.name)#if details != none { meta[ · #details] }],
    meta(item.year),
  )
  #v(-0.15em)
  #bullets(item.bullets)
]

#let education(item) = block(below: 0.75em)[
  #let title = join-items(
    (
      if item.degree.trim() != "" { text(weight: "semibold", item.degree) },
      if item.institution.trim() != "" [#item.institution],
    ),
    meta[, ],
  )
  #split-row(title, meta(fmt-range(item.dates)))
  #if item.location.trim() != "" {
    v(-0.35em)
    text(size: 8.5pt, fill: muted, item.location)
  }
]

#let skills(groups) = grid(
  columns: (auto, 1fr),
  column-gutter: 1em,
  row-gutter: 0.6em,
  ..groups
    .map(group => (text(weight: "medium", group.label), meta(group.items.join(", "))))
    .flatten(),
)

#let certification(item) = block(below: 0.5em)[
  #split-row(
    [#text(weight: "medium", item.name)#if item.issuer.trim() != "" { meta[, #item.issuer] }],
    meta(fmt-date(item.date)),
  )
]

// Header: name and headline left, contact details right.
#grid(
  columns: (1fr, auto),
  column-gutter: 1.5em,
  align: (start + bottom, start + bottom),
  [
    #text(size: 20pt, weight: "semibold", tracking: -0.01em, cv.basics.name)
    #if cv.basics.headline.trim() != "" {
      v(-0.5em)
      text(size: 11pt, fill: accent, cv.basics.headline)
    }
  ],
  text(size: 8.5pt, fill: muted, join-items(contact-items(cv.basics), linebreak())),
)

#if cv.summary.len() > 0 {
  block(above: 1.1em, rich(cv.summary))
}

#for section in cv.sections {
  if not has-items(section) { continue }
  section-heading(section.title)
  if section.kind == "experience" {
    for item in section.experience { experience(item) }
  } else if section.kind == "projects" {
    for item in section.projects { project(item) }
  } else if section.kind == "education" {
    for item in section.education { education(item) }
  } else if section.kind == "skills" {
    skills(section.skills)
  } else if section.kind == "certifications" {
    for item in section.certifications { certification(item) }
  } else {
    bullets(section.custom)
  }
}
