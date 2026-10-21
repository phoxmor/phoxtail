Every page has the same header: `phoxtail_core/page_header.html`, which a
page's own header template extends, filling its blocks as a modal's are
filled. `icon` and `title` name the page (one `h1`, the icon in the brand
colour before the name); `subtitle` is a line of information beside it (the
week on show), centred on it; `controls` holds the search, buttons and
pickers opposite; `below` is a row of its own under both. A block left empty
draws nothing. Its looks are `components/page_header.css`: a step further off
the content (2rem) than the content's parts sit apart. Narrower than 64rem,
the header's own width rather than the screen's, it stacks: the name centred,
its line under it, the controls under both, filling their rows. On the
dashboard, `phoxtail_dashboard/page_header.html` names the page as its menu
entry does, its icon and label; a page under an entry passes `page_title`, a
page with none passes `page_icon` too. The API Tokens, Remotes and Streams
sync admin pages use it, the API Tokens page now with its menu icon.
