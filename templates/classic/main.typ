// Classic: Libertinus Serif, centred header, navy section rules, muted stack beside the
// organisation, dates and locations right-aligned, client engagements as sub-headings.
#import "/_lib/cv.typ": *
#let cv = json("data.json")

#let navy = rgb("#1f3a5f")
#let muted = rgb("#5b6472")

#set document(title: cv.basics.name + " CV", author: cv.basics.name)
#set page(paper: paper-size(), margin: (x: 1.7cm, y: 1.5cm))
#set text(font: "Libertinus Serif", size: 10.5pt, lang: "en", hyphenate: false)
#set par(leading: 0.55em, spacing: 0.75em)
#set list(marker: text(fill: navy)[•], indent: 0.15em, body-indent: 0.5em, spacing: 0.5em)

#let meta(body) = text(fill: muted, body)

#let section-heading(title) = block(above: 1.1em, below: 0.6em, sticky: true)[
  #text(size: 10.5pt, weight: "semibold", fill: navy, tracking: 0.06em, upper(title))
  #v(-0.6em)
  #line(length: 100%, stroke: 0.6pt + navy)
]

#let engagement(item) = pad(left: 0.8em, top: 0.1em)[
  #let label = if item.label.trim() != "" [#item.label: ]
  #split-row(
    text(weight: "semibold")[#label#item.name],
    meta(join-items((item.location, fmt-range(item.dates)), [ · ])),
  )
  #bullets(item.bullets)
]

#let experience(item) = block(below: 0.95em)[
  #let stack = if item.stack.len() > 0 {
    h(0.5em) + text(size: 9pt, fill: muted, item.stack.join(", "))
  }
  #split-row([*#item.org*#stack], meta(item.location))
  #v(-0.5em)
  #split-row(emph(item.role), meta(fmt-range(item.dates)))
  #bullets(item.bullets)
  #for engagement-item in item.engagements { src(engagement-item, engagement(engagement-item)) }
]

#let project(item) = block(below: 0.85em)[
  #let status = if item.status.trim() != "" [ (#item.status)]
  #let url = if item.url != none {
    h(0.5em) + text(size: 9pt, fill: muted, link(item.url, short-url(item.url)))
  }
  #split-row([*#item.name*#status#url], meta(item.year))
  #bullets(item.bullets)
]

#let education(item) = block(below: 0.8em)[
  #split-row([*#item.institution*], meta(item.location))
  #v(-0.5em)
  #split-row(emph(item.degree), meta(fmt-range(item.dates)))
]

#let skills(groups) = grid(
  columns: (auto, 1fr),
  column-gutter: 0.9em,
  row-gutter: 0.55em,
  ..groups.map(group => (src(group, [*#group.label*]), src(group, group.items.join(", ")))).flatten(),
)

#let certification(item) = block(below: 0.55em)[
  #let issuer = if item.issuer.trim() != "" [, #item.issuer]
  #split-row([*#item.name*#issuer], meta(fmt-date(item.date)))
]

// Header
#src("basics", align(center)[
  #text(size: 22pt, weight: "semibold", cv.basics.name)
  #if cv.basics.headline.trim() != "" {
    v(-0.35em)
    text(size: 12pt, fill: muted, cv.basics.headline)
  }
  #v(-0.2em)
  #text(size: 9.5pt, join-items(contact-items(cv.basics), [#h(0.45em)·#h(0.45em)]))
])

#if cv.summary.len() > 0 {
  src("summary", block(above: 1em, rich(cv.summary)))
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
