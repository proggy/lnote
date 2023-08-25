# To Do

- use argparse instead of optparse
- add -l/--line options to select a line or a range of lines
- add a search command (full text search feature), return notebook names
- add a command "clear" (or similar) to delete all temporary directories
- do not overwrite graphic files when submitting a figure, instead rename


## view()

- add -l/--line option to select a line or a range of lines


## figure()

- determine size of the graphics file and choose width and height
  accordingly
- do not overwrite existing graphics files (maybe only by option), instead
  rename the file


## prune()

- negative numbers remove lines from the beginning of the notebook


## opt2dayrange()

- support ranges like "lastweek" or "thisweek" or "nextweek" etc.


# Future Ideas

- work with hardlinks instead of copying the graphics files? Not good if
  renaming will be possible in the future.
