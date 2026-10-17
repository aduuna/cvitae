// Minimal: black and white only, generous whitespace, no rules. Libertinus Serif, with section
// titles set apart by space and weight alone.
#import "/_lib/cv.typ": *
#let cv = json("data.json")

#set document(title: cv.basics.name + " CV", author: cv.basics.name)
#set page(paper: paper-size(), margin: (x: 2.2cm, y: 2cm))
#set text(font: "Libertinus Serif", size: 10.5pt, fill: black, lang: "en", hyphenate: false)
#set par(leading: 0.6em, spacing: 0.85em)
#set list(marker: [–], indent: 0em, body-indent: 0.6em, spacing: 0.55em)
#show link: set text(fill: black)

#let section-heading(title) = block(above: 1.6em, below: 0.8em, sticky: true)[
  #text(size: 11pt, weight: "semibold", title)
]

#let engagement(item) = pad(left: 1em, top: 0.15em)[
  #let label = if item.label.trim() != "" [#item.label: ]
  #split-row(
    [#label#item.name#if item.location.trim() != "" [, #item.location]],
    fmt-range(item.dates),
  )
  #bullets(item.bullets)
]

#let experience(item) = block(below: 1.1em)[
  #split-row([*#item.role*, #item.org], fmt-range(item.dates))
  #let details = join-items((item.location, item.stack.join(", ")), [ · ])
  #if details != none {
    v(-0.45em)
    emph(details)
  }
  #bullets(item.bullets)
  #for engagement-item in item.engagements { src(engagement-item, engagement(engagement-item)) }
]

#let project(item) = block(below: 1em)[
  #let details = join-items(
    (item.status, if item.url != none { link(item.url, short-url(item.url)) }),
    [, ],
  )
  #split-row([*#item.name*#if details != none [, #emph(details)]], item.year)
  #bullets(item.bullets)
]

#let education(item) = block(below: 0.8em)[
  #let title = join-items(
    (
      if item.degree.trim() != "" [*#item.degree*],
      if item.institution.trim() != "" [#item.institution],
    ),
    [, ],
  )
  #split-row(title, fmt-range(item.dates))
  #if item.location.trim() != "" {
    v(-0.45em)
    emph(item.location)
  }
]

#let skills(groups) = grid(
  columns: (auto, 1fr),
  column-gutter: 1.2em,
  row-gutter: 0.7em,
  ..groups.map(group => (src(group, [*#group.label*]), src(group, group.items.join(", ")))).flatten(),
)

#let certification(item) = block(below: 0.6em)[
  #split-row(
    [*#item.name*#if item.issuer.trim() != "" [, #item.issuer]],
    fmt-date(item.date),
  )
]

// Header: name, headline, contact details, all left-aligned.
#src("basics")[
  #text(size: 20pt, cv.basics.name)
  #if cv.basics.headline.trim() != "" {
    v(-0.4em)
    text(size: 11.5pt, cv.basics.headline)
  }
  #v(-0.1em)
  #text(size: 9.5pt, join-items(contact-items(cv.basics), [#h(0.6em)#h(0.6em)]))
]

#if cv.summary.len() > 0 {
  src("summary", block(above: 1.4em, rich(cv.summary)))
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
