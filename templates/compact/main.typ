// Compact: denser spacing and smaller type, for long careers that must fit one page.
#import "/_lib/cv.typ": *
#let cv = json("data.json")

#let ink = rgb("#222222")
#let muted = rgb("#5f6368")
#let rule = rgb("#b8bcc2")

#set document(title: cv.basics.name + " CV", author: cv.basics.name)
#set page(paper: paper-size(), margin: (x: 1.3cm, y: 1.2cm))
#set text(font: "Libertinus Serif", size: 9.5pt, fill: ink, lang: "en", hyphenate: false)
#set par(leading: 0.48em, spacing: 0.6em)
#set list(marker: [–], indent: 0.1em, body-indent: 0.45em, spacing: 0.36em)

#let meta(body) = text(fill: muted, body)

#let section-heading(title) = block(above: 0.85em, below: 0.45em, sticky: true)[
  #grid(
    columns: (auto, 1fr),
    column-gutter: 0.6em,
    align: horizon,
    text(size: 10.5pt, weight: "bold", smallcaps(all: true, title)),
    line(length: 100%, stroke: 0.5pt + rule),
  )
]

#let engagement(item) = pad(left: 0.7em, top: 0.05em)[
  #let label = if item.label.trim() != "" [#item.label: ]
  #split-row(
    [#label#text(weight: "semibold", item.name)#if item.location.trim() != "" [, #item.location]],
    meta(fmt-range(item.dates)),
  )
  #v(-0.25em)
  #bullets(item.bullets)
]

#let experience(item) = block(below: 0.7em)[
  #split-row(
    [*#item.role*, #item.org#if item.location.trim() != "" { meta[, #item.location] }],
    meta(fmt-range(item.dates)),
  )
  #if item.stack.len() > 0 {
    v(-0.3em)
    text(size: 9pt, fill: muted, item.stack.join(" · "))
  }
  #v(-0.25em)
  #bullets(item.bullets)
  #for engagement-item in item.engagements { src(engagement-item, engagement(engagement-item)) }
]

#let project(item) = block(below: 0.6em)[
  #let details = join-items(
    (item.status, if item.url != none { link(item.url, short-url(item.url)) }),
    [ · ],
  )
  #split-row([*#item.name*#if details != none { meta[ · #details] }], meta(item.year))
  #v(-0.25em)
  #bullets(item.bullets)
]

#let education(item) = block(below: 0.5em)[
  #split-row(
    [*#item.degree*, #item.institution#if item.location.trim() != "" { meta[, #item.location] }],
    meta(fmt-range(item.dates)),
  )
]

#let skills(groups) = grid(
  columns: (auto, 1fr),
  column-gutter: 0.7em,
  row-gutter: 0.42em,
  ..groups.map(group => (src(group, [*#group.label*]), src(group, group.items.join(", ")))).flatten(),
)

#let certification(item) = block(below: 0.4em)[
  #split-row(
    [*#item.name*#if item.issuer.trim() != "" { meta[, #item.issuer] }],
    meta(fmt-date(item.date)),
  )
]

// Header: name and headline left, contact details right.
#src("basics", grid(
  columns: (1fr, auto),
  column-gutter: 1.2em,
  align: (start + bottom, end + bottom),
  [
    #text(size: 17pt, weight: "semibold", cv.basics.name)
    #if cv.basics.headline.trim() != "" {
      v(-0.5em)
      text(size: 10.5pt, fill: muted, cv.basics.headline)
    }
  ],
  text(size: 9pt, join-items(contact-items(cv.basics), linebreak())),
))

#if cv.summary.len() > 0 {
  src("summary", block(above: 0.8em, rich(cv.summary)))
}

#sections(
  cv,
  section-heading: section-heading,
  experience: experience,
  project: project,
  education: education,
  skills: skills,
  certification: certification,
)
