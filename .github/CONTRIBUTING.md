# Contributing to byecycle
If you're reading this document, you're probably considering contributing to this project.
That's great, I appreciate that a lot! I hope you can find the help that you're looking
for in the next few sections.

## What is a Contribution?
A [pull request](#pull-request-styleguide) (PR) containing code or documentation for this 
project is the first thing that comes to mind. Writing a good [issue](#issue-styleguide),
or participating in issue or PR discussions is also an active and valuable contribution.

I do not accept money. If you want to get rid of some, please consider donating to other
[open source software](https://github.com/sereneblue/awesome-oss) that sounds good to you.

## Pull Request Guide
Every PR should be preceded by an issue ticket describing the problem that needs
to be solved. That way, subject matter discussion can take place on the ticket, and 
discussions on the PR are constrained to technical matters.

This project squashes branches before merging, so you're free to commit in whichever way
you want. 

Branch names **must** lead with a ticket number followed by a slash, finished by an 
arbitrary branch name. The name **may** lead with the issue type (`bug`, `feat[ure]`, 
`docs`, `chore`).

**Example**

- you notice byecycle crashes if it's given a symlink
- you create an issue where you describe the problem, which receives the number #42
- you fork the project, set up a development environment, and create a branch 
  `42/feat_support_symlinks` from `main`
- you implement the functionality and create a PR
- a maintainer reviews your code, flags issues, suggests changes, etc.
- you give feedback on the review and apply changes
- your PR get merged, and is eventually released 

## Issue Guide
So, you found something that's wrong with my code, huh? I promise I do my best not to take
that personally, but while you work on formulating your complaint, I'd kindly ask to
consider that [there is indeed a human on the receiving end](https://mtlynch.io/human-code-reviews-1/)
who, while they do want your feedback, also benefit from being treated in a humane way 
(the linked article gives guidelines for code reviews, but the principles extend well 
enough to "collaborating on code" in general).
