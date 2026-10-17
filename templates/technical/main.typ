// Technical: Geist for text, Geist Mono accents for stacks, dates and section labels, and the
// skills as a grid of groups.
#import "/_lib/cv.typ": *
#let cv = json("data.json")

#let ink = rgb("#1b1f24")
#let accent = rgb("#0f766e")
#let muted = rgb("#5b636d")
#let rule = rgb("#cfd4da")

#set document(title: cv.basics.name + " CV", author: cv.basics.name)
#set page(paper: paper-size(), margin: (x: 1.5cm, y: 1.3cm))
#set text(font: "Geist", size: 9.5pt, fill: ink, lang: "en", hyphenate: false)
#set par(leading: 0.52em, spacing: 0.65em)
#set list(marker: text(font: "Geist Mono", fill: accent)[>], indent: 0em, body-indent: 0.5em, spacing: 0.42em)
#show link: set text(fill: ink)

#let mono(body, size: 8.5pt, fill: muted) = text(font: "Geist Mono", size: size, fill: fill, body)

#let section-heading(title) = block(above: 1.05em, below: 0.55em, sticky: true)[
  #grid(
    columns: (auto, 1fr),
    column-gutter: 0.6em,
    align: horizon,
    mono(size: 9pt, fill: accent)[\#\# #lower(title)],
    line(length: 100%, stroke: (paint: rule, thickness: 0.5pt, dash: "dotted")),
  )
]

#let engagement(item) = pad(left: 0.9em, top: 0.05em)[
  #let label = if item.label.trim() != "" { mono[#lower(item.label) ] }
  #split-row(
    [#label#text(weight: "medium", item.name)#if item.location.trim() != "" { text(fill: muted)[, #item.location] }],
    mono(fmt-range(item.dates)),
  )
  #v(-0.2em)
  #bullets(item.bullets)
]

#let experience(item) = block(below: 0.85em)[
  #split-row(
    [#text(weight: "semibold", item.role) #text(fill: muted)[\@] #text(weight: "medium", item.org)#if item.location.trim() != "" { text(fill: muted)[, #item.location] }],
    mono(fmt-range(item.dates)),
  )
  #if item.stack.len() > 0 {
    v(-0.3em)
    mono(fill: accent, item.stack.join(" · "))
  }
  #v(-0.15em)
  #bullets(item.bullets)
  #for engagement-item in item.engagements { src(engagement-item, engagement(engagement-item)) }
]

#let project(item) = block(below: 0.75em)[
  #let details = join-items(
    (
      if item.status.trim() != "" { mono[[#item.status]] },
      if item.url != none { mono(link(item.url, short-url(item.url))) },
    ),
    h(0.5em),
  )
  #split-row(
    [#text(weight: "semibold", item.name)#if details != none { h(0.5em) + details }],
    mono(item.year),
  )
  #v(-0.15em)
  #bullets(item.bullets)
]

#let education(item) = block(below: 0.65em)[
  #let title = join-items(
    (
      if item.degree.trim() != "" { text(weight: "semibold", item.degree) },
      if item.institution.trim() != "" [#item.institution],
      if item.location.trim() != "" { text(fill: muted, item.location) },
    ),
    [, ],
  )
  #split-row(title, mono(fmt-range(item.dates)))
]

// Groups side by side, two per row: a mono label above a comma-separated list.
#let skills(groups) = grid(
  columns: (1fr, 1fr),
  column-gutter: 1.4em,
  row-gutter: 0.75em,
  ..groups.map(group => src(group)[
    #mono(fill: accent, lower(group.label))
    #v(-0.45em)
    #group.items.join(", ")
  ]),
)

#let certification(item) = block(below: 0.45em)[
  #split-row(
    [#text(weight: "medium", item.name)#if item.issuer.trim() != "" { text(fill: muted)[, #item.issuer] }],
    mono(fmt-date(item.date)),
  )
]

// Header: name, headline in mono, contact line.
#src("basics")[
  #text(size: 19pt, weight: "semibold", cv.basics.name)
  #if cv.basics.headline.trim() != "" {
    v(-0.45em)
    mono(size: 10pt, fill: accent, cv.basics.headline)
  }
  #v(-0.15em)
  #mono(size: 8.5pt, join-items(contact-items(cv.basics), [ | ]))
]

#if cv.summary.len() > 0 {
  src("summary", block(above: 0.95em, rich(cv.summary)))
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
