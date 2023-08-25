#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright notice
# ----------------
#
# Copyright (C) 2013-2023 Daniel Jung
# Contact: proggy-contact@mailbox.org
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the Free
# Software Foundation; either version 2 of the License, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for
# more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA.
#
"""Compose notes in LaTeX format on the command line. Organize the notes in
notebooks. Automatically create a notebook for the current day if no specific
notebook is selected. View and edit the notes of each day or notebook. Select
one or more notebooks or a certain timerange and export them to a PDF file, or
merge them into a new notebook.

The default data directory is "~/data/lnote". This can be configured by setting
the environment variable LNOTE_DIR.
"""
__version__ = 'v0.1.0'

import glob
import fnmatch
import os
import shutil
import subprocess
import sys
import time
import optparse


# set default data directory, create it if it does not exist
LNOTE_DIR = os.path.expanduser(os.environ.get('LNOTE_DIR', '~/data/lnote'))
if not os.path.isdir(LNOTE_DIR):
    os.makedirs(LNOTE_DIR)


#=====================#
# Command definitions #
#=====================#


def create(*args):
    """Create a notebook."""
    op = optparse.OptionParser(usage='%prog create [options] NAME ' +
                                     '[NAME2 NAME3 ...]',
                               version=__version__,
                               description=create.__doc__)
    op.add_option('-t', '--template', default='', type=str,
                  help='create new notebook from template ' +
                       '(duplicate an existing notebook)')
    op.add_option('-v', '--verbose', default=False, action='store_true',
                  help='be verbose')
    if len(args) == 0:
        args = ['--help']
    opts, posargs = op.parse_args(args=list(args))

    # check if template exists
    if opts.template and not os.path.isdir(os.path.join(LNOTE_DIR, opts.template)):
        print(f'lnote create: template "{opts.template}" not found', file=sys.stderr)
        sys.exit(1)

    for name in posargs:
        # check if notebook with that name already exists
        if name in os.listdir(LNOTE_DIR):
            print('lnote create: cannot create notebook ' +
                  f'"{name}": file exists', file=sys.stderr)
            continue

        # create notebook
        os.mkdir(os.path.join(LNOTE_DIR, name))
        if opts.verbose:
            print(f'mkdir {os.path.join(LNOTE_DIR, name)}')
        dst = os.path.join(LNOTE_DIR, name, name + '.tex')
        if opts.template:
            # copy the template file
            src = os.path.join(LNOTE_DIR, opts.template, opts.template + '.tex')
            shutil.copyfile(src, dst)
            if opts.verbose:
                print(f'cp {src} {dst}')
        else:
            open(dst, 'w').close()
            if opts.verbose:
                print(f'echo -n > {dst}')

        # copy all other files from the template as well
        if opts.template:
            for filename in os.listdir(os.path.join(LNOTE_DIR, opts.template)):
                if filename != opts.template + '.tex':
                    src = os.path.join(LNOTE_DIR, opts.template, filename)
                    dst = os.path.join(LNOTE_DIR, name)
                    shutil.copy(src, dst)
                    if opts.verbose:
                        print(f'cp {src} {dst}')


def listn(*args):
    """List notebooks."""
    op = optparse.OptionParser(usage='%prog list [options] ' +
                                     '[PATTERN [PATTERN2 PATTERN3 ...]]',
                               version=__version__,
                               description=listn.__doc__)
    op.add_option('-l', '--long', default=False, action='store_true',
                  help='use a long listing format. The columns, from left ' +
                       'to right: 1. number of files, ' +
                       '2. linecount of tex-file, ' +
                       '3. total size in bytes, ' +
                       '4. modification time, 5. notebook name')
    opts, posargs = op.parse_args(args=list(args))
    if len(posargs) == 0:
        posargs = ['*']

    # select notebooks according to patterns
    try:
        notebooks = select_notebooks(*posargs, unique=True, forgiving=True)
    except SelectNotebookError as e:
        print(f'lnote list: notebook not found: {e}', file=sys.stderr)
        sys.exit(1)
    notebooks.sort()

    # display selected notebooks
    if opts.long:
        for notebook in notebooks:
            # collect some information about the notebook
            dirsize = get_size(dirpath(notebook))
            dirsize_digits = len(str(get_size(LNOTE_DIR)))
            modtime = get_mtime(dirpath(notebook))
            filecount = len(os.listdir(dirpath(notebook)))
            with open(texpath(notebook), 'r') as f:
                linecount = len(f.readlines())
            print('% 3i % 4i % *i %s %s' \
                  % (filecount, linecount, dirsize_digits, dirsize,
                     time.ctime(modtime), notebook))
    else:
        printcols(notebooks)


def rename(*args):
    """Rename a notebook."""
    op = optparse.OptionParser(usage='%prog rename [options] OLD_NAME ' +
                                     'NEW_NAME',
                               version=__version__,
                               description=rename.__doc__)
    op.add_option('-v', '--verbose', default=False, action='store_true',
                  help='be verbose')
    if len(args) == 0:
        args = ['--help']
    opts, posargs = op.parse_args(args=list(args))
    if len(posargs) != 2:
        print('lnote rename: wrong number of parameters, ' +
              'expecting exactly two (old and new notebook name)', file=sys.stderr)
    old, new = posargs

    # check if notebook exists
    if old not in os.listdir(LNOTE_DIR):
        print(f'lnote rename: cannot rename "{old}": no such file', file=sys.stderr)
        sys.exit(1)

    # check if notebook with that name already exists
    if new in os.listdir(LNOTE_DIR):
        print(f'lnote rename: cannot rename notebook to "{new}": file exists', file=sys.stderr)
        sys.exit(1)

    # rename notebook
    olddir = os.path.join(LNOTE_DIR, old)
    newdir = os.path.join(LNOTE_DIR, new)
    os.rename(olddir, newdir)
    if opts.verbose:
        print(f'mv {olddir} {newdir}')
    oldtex = os.path.join(LNOTE_DIR, new, old + '.tex')
    newtex = os.path.join(LNOTE_DIR, new, new + '.tex')
    os.rename(oldtex, newtex)
    if opts.verbose:
        print(f'mv {oldtex} {newtex}')


def merge(*args):
    """Merge several notebooks into another (append all source notebooks to the
    target notebook). If the target notebook does not exist, create it."""
    op = optparse.OptionParser(usage='%prog merge [options] ' +
                                     'SOURCE_NOTEBOOKS TARGET_NOTEBOOK',
                               version=__version__,
                               description=merge.__doc__)
    op.add_option('-v', '--verbose', default=False, action='store_true',
                  help='be verbose')
    op.add_option('-d', '--date', default=False, action='store_true',
                  help='show date of notebooks as marginal notes')
    if len(args) == 0:
        args = ['--help']
    opts, posargs = op.parse_args(args=list(args))
    notebooks = select_notebooks(*posargs[:-1])
    new = select_notebook(posargs[-1], forgiving=True)

    # check if all notebooks exist
    for notebook in notebooks:
        if notebook not in os.listdir(LNOTE_DIR):
            print('lnote merge: cannot load notebook "{notebook}": no such file', file=sys.stderr)
            sys.exit(1)

    # merge notebooks
    for notebook in notebooks:
        # load tex-file of source notebook and append it to target notebook
        with open(texpath(notebook), 'r') as f:
            lines = f.readlines()
        linebreak('--notebook', new)
        if opts.date:
            marginnote('--notebook', new, '\\texttt{%s}' % notebook)
        append_text(new, ''.join(lines).strip())
        if opts.verbose:
            print(f'cat {texpath(notebook)} >> {texpath(new)}')

        # copy all other files from the source notebook
        for filename in os.listdir(os.path.join(LNOTE_DIR, notebook)):
            if filename != notebook + '.tex':
                src = os.path.join(LNOTE_DIR, notebook, filename)
                dst = os.path.join(LNOTE_DIR, new)
                shutil.copy(src, dst)
                if opts.verbose:
                    print('cp {src} {dst}')


def edit(*args):
    """Open notebook in a text editor. If multiple notebooks are given, open
    them side by side."""
    op = optparse.OptionParser(usage='%prog edit [options] NOTEBOOK ' +
                                     '[NOTEBOOK2 NOTEBOOK3 ...]',
                               version=__version__,
                               description=edit.__doc__)
    op.add_option('-e', '--editor',
                  default=os.environ.get('LNOTE_EDITOR', 'vim'),
                  help='set editor. Default can be overwritten with ' +
                       'environment variable LNOTE_EDITOR')
    opts, posargs = op.parse_args(args=list(args))
    if len(posargs) == 0:
        posargs = [date2filename(*jdn2greg(opt2day('today')))]

    # select notebooks
    notebooks = select_notebooks(*posargs, unique=True)

    # open notebooks side by side
    paths = [texpath(notebook) for notebook in notebooks]
    subprocess.call([opts.editor] + paths, stderr=subprocess.STDOUT,
                    stdout=None if opts.editor in ('vi', 'vim')
                    else open('/dev/null', 'w'))


def delete(*args):
    """Delete a notebook."""
    op = optparse.OptionParser(usage='%prog delete [options] NOTEBOOK ' +
                                     '[NOTEBOOK2 NOTEBOOK3 ...]',
                               version=__version__,
                               description=delete.__doc__)
    op.add_option('-n', '--notebook', default=None, help='select notebook')
    op.add_option('-f', '--force', default=False, action='store_true',
                  help='ignore nonexistent notebooks, never prompt')
    op.add_option('-t', '--test', default=False, action='store_true',
                  help='test mode, only show what would have been deleted')
    if len(args) == 0:
        args = ['--help']
    opts, posargs = op.parse_args(args=list(args))

    # select notebooks
    try:
        notebooks = select_notebooks(*posargs, unique=True,
                                     forgiving=opts.force)
    except SelectNotebookError as e:
        print(f'lnote delete: notebook not found: {e}', file=sys.stderr)
        sys.exit(1)

    # delete notebooks
    for notebook in notebooks:
        # prompt
        if not opts.test and not opts.force:
            message = f'delete notebook "{notebook}"? '
            answer = input(message).lower()
            if not answer or not 'yes'.startswith(answer):
                continue

        # delete
        if opts.test:
            print(f'would have deleted "{notebook}"')
        else:
            shutil.rmtree(os.path.join(LNOTE_DIR, notebook))


def export(*args):
    """Export a notebook or selection of notebooks (for now only to PDF
    format)."""

    op = optparse.OptionParser(usage='%prog export [options] ' +
                                     '[PATTERN [PATTERN2 PATTERN3 ...]] ' +
                                     'OUTPUT_FILE',
                               version=__version__,
                               description=export.__doc__)
    op.add_option('-m', '--export-merge', dest='mergetemp',
                  default='temp-export-merge',
                  help='set temporary notebook name that is used to merge ' +
                       'the selected notebooks')
    op.add_option('-c', '--export-compile', dest='compiletemp',
                  default='/tmp/export-compile',
                  help='set temporary directory that is used to compile the ' +
                       'LaTeX file of the merged notebook')
    op.add_option('-v', '--verbose', default=False, action='store_true',
                  help='be verbose, print compiler messages')
    op.add_option('-d', '--date', default=False, action='store_true',
                  help='show date of notebooks as marginal notes')
    if len(args) == 0:
        args = ['--help']
    opts, posargs = op.parse_args(args=list(args))
    if len(posargs) == 1:
        posargs = ['today', posargs[0]]

    # select notebooks
    notebooks = select_notebooks(*posargs[:-1])
    if len(notebooks) == 0:
        print('lnote export: no notebook selected', file=sys.stderr)
        sys.exit(1)

    # select target
    target = posargs[-1]
    if '.' not in target:
        target += '.pdf'

    # merge notebooks into temporary notebook
    delete(opts.mergetemp, '--force')
    mergeargs = notebooks + [opts.mergetemp]
    if opts.date:
        mergeargs.append('--date')
    merge(*mergeargs)

    # copy files over to temporary compile directory
    #if os.path.exists(opts.compiletemp): ## aux file must not be deleted
        #shutil.rmtree(opts.compiletemp)
    if not os.path.exists(opts.compiletemp):
        os.makedirs(opts.compiletemp)
    for filename in os.listdir(dirpath(opts.mergetemp)):
        if filename != opts.mergetemp + '.tex':
            src = os.path.join(dirpath(opts.mergetemp), filename)
            shutil.copy(src, opts.compiletemp)

    # add LaTeX preample and epilog to the tex-file and copy it over
    preamble = r'\\documentclass{scrartcl}\\n' + \
               r'\\usepackage{amsmath}\n\\usepackage{amsthm}\n' + \
               r'\\usepackage{graphicx}\n\\usepackage{commath}\n' + \
               r'\\begin{document}\\n\\n'
    epilog = r'\\end{document}'
    with open(texpath(opts.mergetemp), 'r') as f:
        lines = f.readlines()
    with open(os.path.join(opts.compiletemp, opts.mergetemp+'.tex'), 'w') as f:
        f.write(preamble.strip()+'\n')
        f.write(''.join(lines).strip()+'\n')
        f.write(epilog+'\n')

    # use pdflatex to compile PDF document
    cdcmd = 'cd %s' % opts.compiletemp
    latexcmd = 'pdflatex %s' % opts.mergetemp + '.tex'
    #os.system('%s;%s' % (cdcmd, latexcmd))
    subprocess.call(f'{cdcmd};{latexcmd}', shell=True,
                    stderr=None if opts.verbose else subprocess.STDOUT,
                    stdout=None if opts.verbose else open('/dev/null', 'w'))
    try:
        shutil.copyfile(os.path.join(opts.compiletemp, opts.mergetemp+'.pdf'), target)
    except IOError:
        print('lnote export: export failed' +
            ('' if opts.verbose else ', use --verbose to get details'), file=sys.stderr)


def path(*args):
    """Get path of the directory of a certain notebook.
    """
    op = optparse.OptionParser(usage='%prog path [options] NOTEBOOK ' +
                                     '[NOTEBOOK2 NOTEBOOK3 ...]',
                               version=__version__, description=view.__doc__)
    op.add_option('-t', '--tex', default=False, action='store_true',
                  help='get path of the tex file instead of the directory')
    opts, posargs = op.parse_args(args=list(args))
    if len(posargs) == 0:
        posargs = ['today']

    # select notebooks
    notebooks = select_notebooks(*posargs)
    if len(notebooks) == 0:
        print('lnote path: no notebook selected', file=sys.stderr)
        sys.exit(1)

    if opts.tex:
        for notebook in notebooks:
            print(texpath(notebook))
    else:
        for notebook in notebooks:
            print(dirpath(notebook))


def view(*args):
    """View a notebook or a selection of notebooks."""
    op = optparse.OptionParser(usage='%prog view [options] NOTEBOOK ' +
                                     '[NOTEBOOK2 NOTEBOOK3 ...]',
                               version=__version__, description=view.__doc__)
    op.add_option('-e', '--export', default=False, action='store_true',
                  help='view exported version (for now only PDF)')
    op.add_option('-p', '--pdfviewer',
                  default=os.environ.get('LNOTE_PDFVIEWER', 'okular'),
                  help='set PDF viewer. Default can be overwritten with ' +
                       'environment variable LNOTE_PDFVIEWER')
    op.add_option('-m', '--view-merge', dest='mergetemp',
                  default='temp-view-merge',
                  help='set temporary notebook name that is used to merge ' +
                       'the selected notebooks')
    op.add_option('-c', '--view-compile', dest='compiletemp',
                  default='/tmp/view-compile',
                  help='set temporary directory that is used to compile the ' +
                       'LaTeX file of the merged notebook')
    op.add_option('-v', '--verbose', default=False, action='store_true',
                  help='be verbose, print compiler messages')
    op.add_option('-d', '--date', default=False, action='store_true',
                  help='show date of notebooks as marginal notes')

    opts, posargs = op.parse_args(args=list(args))
    if len(posargs) == 0:
        posargs = ['today']

    # select notebooks
    notebooks = select_notebooks(*posargs)
    if len(notebooks) == 0:
        print('lnote view: no notebook selected', file=sys.stderr)
        sys.exit(1)

    if opts.export:
        # compile the LaTeX file of the selected notebooks
        pdffile = os.path.join(dirpath(opts.mergetemp), opts.mergetemp+'.pdf')
        exportargs = notebooks+[pdffile, '--export-merge', opts.mergetemp,
                                '--export-compile', opts.compiletemp]
        if opts.verbose:
            exportargs.append('--verbose')
        if opts.date:
            exportargs.append('--date')
        export(*exportargs)

        # open the PDF file in a PDF viewer (if not already open)
        lines = subprocess.check_output('ps aux',
                                        shell=True).strip().splitlines()
        for line in lines:
            if opts.pdfviewer in line and pdffile in line:
                if opts.verbose:
                    print(f'lnote view: document still open in PID {line.split()[1]}')
                break
        else:
            subprocess.call(f'{opts.pdfviewer} {pdffile} &', shell=True,
                            stderr=None if opts.verbose else subprocess.STDOUT,
                            stdout=None if opts.verbose else open('/dev/null', 'w'))
    else:
        # merge notebooks into temporary notebook and display the tex-file
        delete(opts.mergetemp, '--force')
        mergeargs = notebooks+[opts.mergetemp]
        if opts.date:
            mergeargs.append('--date')
        merge(*mergeargs)
        with open(texpath(opts.mergetemp), 'r') as f:
            text = ''.join(f.readlines())
            if text[0] == '\n':
                text = text[1:]
            if text[-1] == '\n':
                text = text[:-1]
            print(text)


def text(*args):
  """Add text to a notebook. This can be any LaTeX-compatible code.

  If the selected notebook does not exist, it is created. By default, today's
  notebook is used."""
  op = optparse.OptionParser(usage='%prog text [options] TEXT...',
                             version=__version__, description=text.__doc__)
  op.add_option('-n', '--notebook', default=None, help='select notebook')
  op.add_option('-f', '--file', default=None,
                help='read text from the given text file')
  op.add_option('-i', '--stdin', default=False, action='store_true',
                help='read text from standard input')
  if len(args) == 0:
    args = ['--help']
  op.allow_interspersed_args = False
  opts, posargs = op.parse_args(args=list(args))

  # select notebook
  try:
    notebook = select_notebook(opts.notebook)
  except SelectNotebookError:
    print(f'lnote text: notebook not found: {opts.notebook}', file=sys.stderr)
    sys.exit(1)

  # append text from command line arguments
  append_text(notebook, ' '.join(posargs))

  # append text from the given text file
  if opts.file:
    append_text(notebook, open(opts.file, 'r').read())

  # read text from standard input
  if opts.stdin:
    stdin = sys.stdin.read().strip()
    append_text(notebook, stdin)


def linebreak(*args):
  """Add a linebreak (an empty line) to a notebook.

  If the selected notebook does not exist, it is created. By default, today's
  notebook is used."""
  op = optparse.OptionParser(usage='%prog linebreak [options]',
                             version=__version__,
                             description=linebreak.__doc__)
  op.add_option('-n', '--notebook', default=None, help='select notebook')
  op.add_option('-#', '--number', default=1, type=int,
                help='set number of linebreaks')
  op.allow_interspersed_args = False
  opts, posargs = op.parse_args(args=list(args))
  if len(posargs) != 0:
    print('lnote linebreak: not expecting any positional parameters', file=sys.stderr)
    sys.exit(1)
  if opts.number < 0:
    op.error('bad number of linebreaks: %i. ' % opts.number+\
             'Must be non-negative integer')

  # select notebook
  notebook = select_notebook(opts.notebook)

  # append empty lines
  for i in range(opts.number):
    append_text(notebook, '\n')


def section(*args):
  """Add a section to a notebook.

  If the selected notebook does not exist, it is created. By default, today's
  notebook is used."""
  op = optparse.OptionParser(usage='%prog section [options] TITLE...',
                             version=__version__,
                             description=section.__doc__)
  op.add_option('-n', '--notebook', default=None, help='select notebook')
  op.add_option('-l', '--level', default=1, type=int, help='set level')
  op.add_option('-#', '--numbered', default=False, action='store_true',
                help='add numbered section')
  op.allow_interspersed_args = False
  opts, posargs = op.parse_args(args=list(args))

  # determine section level
  if opts.level == 1:
    texcmd = 'section'
  elif opts.level == 2:
    texcmd = 'subsection'
  elif opts.level == 3:
    texcmd = 'subsubsection'
  else:
    op.error('bad section level: %i. Must be out of (1, 2, 3)' % opts.level)

  # numbered sections
  if not opts.numbered:
    texcmd += '*'

  # select notebook
  notebook = select_notebook(opts.notebook)

  # add the section
  title = ' '.join(posargs)
  linebreak('--notebook', notebook) #'--number', '3'
  text('--notebook', notebook, '\%s{%s}' % (texcmd, title))


def paragraph(*args):
  """Add a titled paragraph to a notebook.

  If the selected notebook does not exist, it is created. By default, today's
  notebook is used."""
  op = optparse.OptionParser(usage='%prog paragraph [options] TITLE...',
                             version=__version__,
                             description=paragraph.__doc__)
  op.add_option('-n', '--notebook', default=None, help='select notebook')
  op.add_option('-l', '--level', default=1, type=int, help='set level')
  op.allow_interspersed_args = False
  opts, posargs = op.parse_args(args=list(args))

  # determine section level
  if opts.level == 1:
    texcmd = 'paragraph'
  elif opts.level == 2:
    texcmd = 'subparagraph'
  else:
    op.error('bad paragraph level: %i. Must be out of (1, 2)' % opts.level)

  # select notebook
  notebook = select_notebook(opts.notebook)

  # add the paragraph
  title = ' '.join(posargs)
  linebreak('--notebook', notebook)
  text('--notebook', notebook, '\%s{%s}' % (texcmd, title))


def equation(*args):
  """Add an equation to a notebook.

  If the selected notebook does not exist, it is created. By default, today's
  notebook is used."""
  op = optparse.OptionParser(usage='%prog equation [options] TITLE...',
                             version=__version__,
                             description=equation.__doc__)
  op.add_option('-n', '--notebook', default=None, help='select notebook')
  op.add_option('-#', '--numbered', default=False, action='store_true',
                help='add numbered equation')
  op.add_option('-l', '--label', default='', help='set label')
  op.allow_interspersed_args = False
  opts, posargs = op.parse_args(args=list(args))

  # select notebook
  notebook = select_notebook(opts.notebook)

  # add the equation
  eq = ' '.join(posargs)
  s = '' if opts.numbered else '*'
  text('--notebook', notebook, '\\begin{equation%s}' % s)
  text('--notebook', notebook, eq)
  if opts.label:
    text('--notebook', notebook, '\label{%s}' % opts.label)
  text('--notebook', notebook, '\\end{equation%s}' % s)


def figure(*args):
  """Add a figure to a notebook.

  If the selected notebook does not exist, it is created. By default, today's
  notebook is used."""
  op = optparse.OptionParser(usage='%prog figure [options] TITLE...',
                             version=__version__,
                             description=figure.__doc__)
  op.add_option('-n', '--notebook', default=None, help='select notebook')
  op.add_option('-c', '--caption', default='', help='set caption')
  op.add_option('-l', '--label', default='', help='set label')
  opts, posargs = op.parse_args(args=list(args))

  # select notebook
  notebook = select_notebook(opts.notebook)

  # check if all graphics files exist
  for graphicsfile in posargs:
    if not os.path.isfile(graphicsfile):
      print(f'lnote figure: cannot copy {graphicsfile}: no such file', file=sys.stderr)
      sys.exit(1)

  # add the figure
  linebreak('--notebook', notebook)
  text('--notebook', notebook, '\\begin{figure}')
  text('--notebook', notebook, '\centering')
  for graphicsfile in posargs:
    # copy the graphics file into the notebook directory
    shutil.copy(graphicsfile, os.path.join(LNOTE_DIR, notebook))

    # add graphics file
    text('--notebook', notebook, '\includegraphics[width=.72\\textwidth]{%s}'\
                                 % os.path.basename(graphicsfile))
  if opts.caption:
    text('--notebook', notebook, '\caption{%s}' % opts.caption)
  if opts.label:
    text('--notebook', notebook, '\label{%s}' % opts.label)
  else:
    if len(posargs) == 1:
      text('--notebook', notebook,
           '\label{%s}' % os.path.basename(posargs[0]).rsplit('.', 1)[0])
  text('--notebook', notebook, '\\end{figure}')


def prune(*args):
  """Remove the last line of a notebook.

  If the selected notebook does not exist, it is created. By default, today's
  notebook is used."""
  op = optparse.OptionParser(usage='%prog prune [options]',
                             version=__version__,
                             description=prune.__doc__)
  op.add_option('-n', '--notebook', default=None, help='select notebook')
  op.add_option('-#', '--number', default=1, type=int,
                help='set number of lines to remove')
  op.add_option('-f', '--force', default=False, action='store_true',
                help='never prompt')
  op.allow_interspersed_args = False
  opts, posargs = op.parse_args(args=list(args))
  if len(posargs) != 0:
    print('lnote prune: not expecting any positional parameters', file=sys.stderr)
    sys.exit(1)
  if opts.number < 0:
    op.error(f'bad number of lines: {opts.number}. Must be non-negative integer')
  if opts.number == 0:
    return

  # select notebook
  notebook = select_notebook(opts.notebook)

  # copy the whole file, but leave out the last couple of lines
  with open(texpath(notebook), 'r') as f:
    lines = f.readlines()
  if len(lines[-opts.number:]) == 0:
    return

  # prompt
  if not opts.force:
    # print the lines
    select = ''.join(lines[-opts.number:]) #.strip()
    sys.stdout.write('\033[7m%s\033[0m' % select)

    message = 'remove the above line%s from notebook "%s"? ' \
              % (plural(opts.number), notebook)
    answer = input(message).lower()
    if not answer or not 'yes'.startswith(answer):
      return

  # overwrite tex-file, leave out the last couple of lines
  with open(texpath(notebook), 'w') as f:
    for line in lines[:-opts.number]:
      f.write(line)


def item(*args):
  """Add a list item to a notebook. If the notebook ends with a list of the
  chosen type, continue that list.

  If the selected notebook does not exist, it is created. By default, today's
  notebook is used."""
  op = optparse.OptionParser(usage='%prog item [options] TEXT...',
                             version=__version__, description=item.__doc__)
  op.add_option('-n', '--notebook', default=None, help='select notebook')
  op.add_option('-t', '--type', default='itemize', help='set list type')
  op.add_option('-l', '--label', default=None, type=str, help='set label')
  op.allow_interspersed_args = False
  opts, posargs = op.parse_args(args=list(args))

  ITEMIZE = 1
  ENUMERATE = 2
  DESCRIPTION = 3
  if 'itemize'.startswith(opts.type.lower()):
    listtype = ITEMIZE
  elif 'enumerate'.startswith(opts.type.lower()):
    listtype = ENUMERATE
  elif 'description'.startswith(opts.type.lower()):
    listtype = DESCRIPTION
  else:
    print(f'lnote item: unknown list type: {opts.type}', file=sys.stderr)
    sys.exit(1)
  if listtype is ITEMIZE:
    listtypename = 'itemize'
  elif listtype is ENUMERATE:
    listtypename = 'enumerate'
  elif listtype is DESCRIPTION:
    listtypename = 'description'

  # select notebook
  try:
    notebook = select_notebook(opts.notebook)
  except SelectNotebookError:
    print(f'lnote list: notebook not found: {opts.notebook}', file=sys.stderr)
    sys.exit(1)

  # check last line of the notebook
  with open(texpath(notebook), 'r') as f:
    lines = f.readlines()
  #while not lines[-1].strip():
    #lines = lines[:-1]
  if lines and '\\end{%s}' % listtypename in lines[-1]:
    prune('--notebook', notebook, '--force')
  else:
    append_text(notebook, '\\begin{%s}' % listtypename)

  # append item
  if opts.label is None:
    append_text(notebook, '\\item %s' % ' '.join(posargs))
  else:
    append_text(notebook, '\\item[%s] %s' % (opts.label, ' '.join(posargs)))

  # end list environment
  append_text(notebook, '\\end{%s}' % listtypename)


def marginnote(*args):
  """Add a marginal note to the notebook (using the LaTeX command
  "marginpar").

  If the selected notebook does not exist, it is created. By default, today's
  notebook is used."""
  op = optparse.OptionParser(usage='%prog marginnote [options] TEXT...',
                             version=__version__,
                             description=marginnote.__doc__)
  op.add_option('-n', '--notebook', default=None, help='select notebook')
  op.allow_interspersed_args = False
  opts, posargs = op.parse_args(args=list(args))

  # select notebook
  notebook = select_notebook(opts.notebook)

  # add the marginal note
  notetext = ' '.join(posargs)
  text('--notebook', notebook, '\marginpar{%s}' % notetext)


#=====================#
# Auxiliary functions #
#=====================#


def printcols(strlist, ret=False):
  """Print the strings in the given list in column by column (similar the bash
  command "ls"), respecting the width of the shell window. If ret is True, give
  back the resulting string instead of printing it to stdout."""
  if len(strlist) == 0:
    return
  numstr = len(strlist)
  cols = get_cols()
  maxwidth = max([len(s) for s in strlist])
  numcols = cols // (maxwidth + 2)
  numrows = int(ceil(numstr / numcols))

  # print the list
  result = ''
  for rind in range(numrows):
    for cind in range(numcols):
      sind = cind * numrows + rind
      if sind < numstr:
        result += strlist[sind] + ' ' * (maxwidth - len(strlist[sind]) + 2)
    result = result.rstrip() + '\n'

  # return or print result
  if ret:
    return result.rstrip()
  else:
    print(result.rstrip())


def ceil(x):
    """Return the ceiling of x. This exists as a substitute for numpy.ceil, to
    avoid importing the huge numpy module just for this function."""
    if int(x) == x or x <= 0:
        return int(x)
    else:
        return int(x)+1


def get_cols():
    try:
        return int(subprocess.getoutput('tput cols'))
    except ValueError:
        # return default width
        return 80


#def require_file(filename):
  #"""If the file does not exist, create it, and also all directories along the
  #given path."""
  #filename = os.path.expanduser(filename)
  #if not os.path.isfile(filename):
    #path, fname = os.path.split(filename)
    #if not os.path.isdir(path):
      #os.makedirs(path)
    #open(filename, 'w').close()
  #if not os.path.isfile(filename):
    #raise IOError('unable to create file')


#def require_day(day):
  #"""If the tex-file and the directory for the given day do not yet exist,
  #create them."""
  #require_file(texpath(day))


def texpath(notebook):
  """Return the path to the tex-file of the given notebook."""
  return os.path.join(LNOTE_DIR, notebook, notebook + '.tex')


def dirpath(notebook):
  """Return the path to the directory of the given notebook."""
  return os.path.join(LNOTE_DIR, notebook)


#def append_linebreak(notebook):
  #"""Append linebreak to the given notebook."""
  #with open(texpath(notebook), 'a') as texfile:
    #texfile.write(' a\n')


def append_text(notebook, text):
  """Append text to the given notebook."""
  if text != '\n':
    text = text.strip()
    text += '\n'
  with open(texpath(notebook), 'a') as texfile:
    texfile.write(text)


class DayFormatError(BaseException):
  pass


def opt2day(opt):
  """Convert option string to a certain date. Return as Julian day number
  (integer)."""
  opt = opt.strip()
  now = time.localtime()

  if 'today'.startswith(opt.lower()):
    return greg2jdn(now.tm_year, now.tm_mon, now.tm_mday)
  elif 'yesterday'.startswith(opt.lower()):
    return greg2jdn(now.tm_year, now.tm_mon, now.tm_mday)-1
  elif 'tomorrow'.startswith(opt.lower()):
    return greg2jdn(now.tm_year, now.tm_mon, now.tm_mday)+1
  elif 'first'.startswith(opt.lower()):
    possible = fnmatch.filter(os.listdir(LNOTE_DIR), '????-??-??')
    possible.sort()
    first = possible[0]
    year, mon, mday = first.split('-')
    thatday = greg2jdn(year, mon, mday)
    return thatday, thatday+1
  elif 'last'.startswith(opt.lower()):
    possible = fnmatch.filter(os.listdir(LNOTE_DIR), '????-??-??')
    possible.sort()
    last = possible[-1]
    year, mon, mday = last.split('-')
    return greg2jdn(year, mon, mday)
  elif opt.count('/') == 2:
    format = '%Y/%m/%d' if len(opt.split('/')[0]) == 4 else '%y/%m/%d'
    try:
        then = time.strptime(opt, format)
    except ValueError:
        raise DayFormatError(f'bad day format: {opt}')
    return greg2jdn(then.tm_year, then.tm_mon, then.tm_mday)
  elif opt.count('-') == 2:
    format = '%Y-%m-%d' if len(opt.split('-')[0]) == 4 else '%y-%m-%d'
    try:
        then = time.strptime(opt, format)
    except ValueError:
        raise DayFormatError(f'bad day format: {opt}')
    return greg2jdn(then.tm_year, then.tm_mon, then.tm_mday)
  elif opt.count('.') == 2:
    if opt[-1] == '.':
      opt += str(now.tm_year)
    format = '%d.%m.%Y' if len(opt.split('.')[-1]) == 4 else '%d.%m.%y'
    try:
        then = time.strptime(opt, format)
    except ValueError:
        raise DayFormatError(f'bad day format: {opt}')
    return greg2jdn(then.tm_year, then.tm_mon, then.tm_mday)
  else:
    raise DayFormatError(f'bad day format: {opt}')


def opt2days(opt):
  """Convert option string to a list of dates. Return list of integers
  (Julian day numbers)."""
  return [opt2day(x) for x in opt.split(',')]


class DayRangeFormatError(DayFormatError):
  pass


def opt2dayrange(opt):
  """Convert option string to a timerange. Return as tuple with two integers
  (JDN1, JDN2+1) (Julian day numbers)."""
  opt = opt.strip()
  months = ['january', 'february', 'march', 'april', 'may', 'june', 'july',
            'august', 'september', 'october', 'november', 'december']
  now = time.localtime()
  try:
    if not opt:
      # return "empty" range, not selecting any days
      return (opt2day('today'),) * 2
    if opt.count('-') > 1:
      raise ValueError('only one dash (-) allowed in timerange')
    if opt.count('-') == 1:
      begin, end = opt.split('-')
      for m, mon in enumerate(months):
        if begin and mon.startswith(begin.lower()):
          rbegin = greg2jdn(now.tm_year, m+1, 1)
          break
      else:
        if 'today'.startswith(begin.lower()):
          rbegin = greg2jdn(now.tm_year, now.tm_mon, now.tm_mday)
        elif 'yesterday'.startswith(begin.lower()):
          rbegin = greg2jdn(now.tm_year, now.tm_mon, now.tm_mday)-1
        elif 'tomorrow'.startswith(begin.lower()):
          rbegin = greg2jdn(now.tm_year, now.tm_mon, now.tm_mday)+1
        elif 'first'.startswith(begin.lower()):
          possible = fnmatch.filter(os.listdir(LNOTE_DIR), '????-??-??')
          possible.sort()
          first = possible[0]
          year, mon, mday = first.split('-')
          rbegin = greg2jdn(year, mon, mday)
        elif begin and begin.count('/')+begin.count('-')+begin.count('.') == 0:
          rbegin = greg2jdn(int(begin), 1, 1)
        elif begin and begin.count('/') == 1:
          year, mon = begin.split('/')
          rbegin = greg2jdn(year, mon, 1)
        else:
          rbegin = opt2day(begin) if begin else 0
      for m, mon in enumerate(months):
        if end and mon.startswith(end.lower()):
          rend = greg2jdn(now.tm_year, m+2, 1)
          break
      else:
        if 'today'.startswith(end.lower()):
          rend = greg2jdn(now.tm_year, now.tm_mon, now.tm_mday)+1
        elif 'yesterday'.startswith(end.lower()):
          rend = greg2jdn(now.tm_year, now.tm_mon, now.tm_mday)
        elif 'tomorrow'.startswith(end.lower()):
          rend = greg2jdn(now.tm_year, now.tm_mon, now.tm_mday)+2
        elif 'last'.startswith(end.lower()):
          possible = fnmatch.filter(os.listdir(LNOTE_DIR), '????-??-??')
          possible.sort()
          last = possible[-1]
          year, mon, mday = last.split('-')
          rend = greg2jdn(year, mon, mday)+1
        elif end and end.count('/')+end.count('-')+end.count('.') == 0:
          rend = greg2jdn(int(end)+1, 1, 1)
        elif end and end.count('/') == 1:
          year, mon = end.split('/')
          rend = greg2jdn(year, int(mon)+1, 1)
        else:
          rend = opt2day(end)+1 if end else opt2day('today')+1
      return rbegin, rend
    else:
      for m, mon in enumerate(months):
        if mon.startswith(opt.lower()):
          return greg2jdn(now.tm_year, m+1, 1), greg2jdn(now.tm_year, m+2, 1)
      else:
        if 'today'.startswith(opt.lower()):
          today = greg2jdn(now.tm_year, now.tm_mon, now.tm_mday)
          return today, today+1
        elif 'yesterday'.startswith(opt.lower()):
          yesterday = greg2jdn(now.tm_year, now.tm_mon, now.tm_mday)-1
          return yesterday, yesterday+1
        elif 'tomorrow'.startswith(opt.lower()):
          tomorrow = greg2jdn(now.tm_year, now.tm_mon, now.tm_mday)+1
          return tomorrow, tomorrow+1
        elif 'first'.startswith(opt.lower()):
          possible = fnmatch.filter(os.listdir(LNOTE_DIR), '????-??-??')
          possible.sort()
          first = possible[0]
          year, mon, mday = first.split('-')
          thatday = greg2jdn(year, mon, mday)
          return thatday, thatday+1
        elif 'last'.startswith(opt.lower()):
          possible = fnmatch.filter(os.listdir(LNOTE_DIR), '????-??-??')
          possible.sort()
          last = possible[-1]
          year, mon, mday = last.split('-')
          thatday = greg2jdn(year, mon, mday)
          return thatday, thatday+1
        elif opt and opt.count('/')+opt.count('-')+opt.count('.') == 0:
          return greg2jdn(int(opt), 1, 1), greg2jdn(int(opt)+1, 1, 1)
        elif opt and opt.count('/') == 1:
          year, mon = opt.split('/')
          return greg2jdn(year, mon, 1), greg2jdn(year, int(mon)+1, 1)
        else:
          j = opt2day(opt)
          return j, j+1
  except (DayFormatError, ValueError):
    raise DayRangeFormatError(f'bad dayrange format: {opt}')


def opt2dayranges(opt):
  """Convert option string to a list of timeranges. Return as list of tuples
  with two integers (JDN1, JDN2+1) (Julian day numbers)."""
  return [opt2dayrange(x) for x in opt.split(',')]


def greg2jdn(year, mon, mday):
  """Convert Gregorian date to Julian day number.
  Reference: http://en.wikipedia.org/wiki/Julian_Date"""
  year, mon, mday = int(year), int(mon), int(mday)
  a = (14 - mon) // 12
  y = year + 4800 - a
  m = mon + 12 * a - 3
  return mday + (153 * m + 2) // 5 + 365 * y + y // 4 - y // 100 + y // 400 - 32045


def jdn2greg(jdn):
  """Convert Julian day number to Gregorian date.
  Reference: http://en.wikipedia.org/wiki/Julian_Date"""
  J = int(jdn + .5)
  j = J + 32044
  g = j // 146097;                dg = j % 146097
  c = (dg // 36524 + 1) * 3 // 4; dc = dg - c * 36524
  b = dc // 1461;                 db = dc % 1461
  a = (db // 365 + 1) * 3 // 4;   da = db - a * 365
  y = g * 400 + c * 100 + b * 4 + a
  m = (da * 5 + 308) // 153 - 2
  d = da - (m + 4) * 153 // 5 + 122
  year = y - 4800 + (m + 2) // 12
  mon = (m + 2) % 12 + 1
  mday = d + 1
  return year, mon, mday


def date2filename(year, mon, mday):
  """Convert Gregorian date to filename."""
  return '%04i-%02i-%02i' % (year, mon, mday)


def select_notebook(pattern, forgiving=False):
  """Select a single notebook based on the given pattern. If forgiving is
  True, create a new notebook if the given one doesn't exist. Otherwise, only
  create a new notebook if pattern is None or empty."""
  if pattern:
    # try to find a notebook with that name
    if pattern in os.listdir(LNOTE_DIR):
      notebook = pattern
    else:
      # try to interprete string as a day
      try:
        year, mon, mday = jdn2greg(opt2day(pattern))
        notebook = date2filename(year, mon, mday)
        if notebook not in os.listdir(LNOTE_DIR):
          create(notebook)
      except DayFormatError:
        if forgiving:
          notebook = pattern
          create(notebook)
        else:
          raise SelectNotebookError(pattern)
  else:
    # use today
    year, mon, mday = jdn2greg(opt2day('today'))
    notebook = date2filename(year, mon, mday)
    if notebook not in os.listdir(LNOTE_DIR):
      create(notebook)
  return notebook


class SelectNotebookError(BaseException):
  pass

def select_notebooks(*patterns, **kwargs):
  """Select notebooks based on the given string patterns. If unique is True,
  each notebook will be added to the list only once. If skipmissing is True,
  no exception is raised if there is nothing found for a pattern."""

  # get keyword arguments
  unique = kwargs.pop('unique', False)
  forgiving = kwargs.pop('forgiving', False)
  if len(kwargs) != 0:
    raise TypeError(f'select_notebooks() got an unexpected keyword argument \'{list(kwargs.keys())[0]}\'')

  notebooks = []
  for pattern in patterns:
    # first try to glob
    raised = False
    try:
        results = glob.glob(os.path.join(LNOTE_DIR, pattern))
    except:
        raised = True
    if not raised and len(results) != 0:
        #results.sort()
        for result in results:
            notebook = os.path.basename(result)
            if not unique or notebook not in notebooks:
                notebooks.append(notebook)
    else:
        # try to interprete the pattern as a day or dayrange
        try:
            dayrange = opt2dayrange(pattern)
        except DayRangeFormatError:
            if forgiving:
                continue
            else:
                raise SelectNotebookError(pattern)

        # select all notebooks according to dayrange
        dirnames = os.listdir(LNOTE_DIR)
        dirnames.sort()
        for dirname in dirnames:
            try:
               date = time.strptime(dirname, '%Y-%m-%d')
            except ValueError:
               continue
            jdn = greg2jdn(date.tm_year, date.tm_mon, date.tm_mday)
            if jdn >= dayrange[0] and jdn < dayrange[1]:
                if not unique or dirname not in notebooks:
                    notebooks.append(dirname)
  return notebooks


def plural(number):
  """If abs(number) == 1, return "", otherwise return "s". For conveniently
  appending the plural "s" to words depending on some number."""
  return '' if abs(number) == 1 else 's'


def get_size(path):
    """Return total size of a file or directory in bytes.

    Reference:
    http://stackoverflow.com/questions/1392413/calculating-a-directory-size-using-python
    """
    if os.path.isdir(path):
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                total_size += os.path.getsize(fp)
        return total_size
    elif os.path.isfile(path):
        return os.path.getsize(path)
    else:
        return -1


def get_mtime(path):
    """Return last modification time of a file or all files within a directory
    tree (in seconds since the epoch).
    """
    if os.path.isdir(path):
        mtime = os.path.getmtime(path)
        for dirpath, dirnames, filenames in os.walk(path):
            newmtime = os.path.getmtime(dirpath)
            if newmtime > mtime:
                mtime = newmtime
            for f in filenames:
                fp = os.path.join(dirpath, f)
                newmtime = os.path.getmtime(fp)
                if newmtime > mtime:
                    mtime = newmtime
        return mtime
    elif os.path.isfile(path):
        return os.path.getmtime(path)
    else:
        return -1


#==============#
# Main program #
#==============#


# map commands (second element of sys.argv) to functions
_cmd2func = {
             ## here, positional parameters are notebooks ##
             'create'    : create,
             'c'         : create,
             'delete'    : delete,
             'd'         : delete,
             'rename'    : rename,
             'r'         : rename,
             'list'      : listn,
             'l'         : listn,
             'edit'      : edit,
             'e'         : edit,
             'merge'     : merge,
             'm'         : merge,
             'export'    : export,
             'x'         : export,
             'view'      : view,
             'v'         : view,
             'path'      : path,

             ## here, positional parameters are not notebooks but text ##
             ## instead, notebooks are selected using the -n option    ##
             'text'      : text,
             't'         : text,
             'linebreak' : linebreak,
             'b'         : linebreak,
             'equation'  : equation,
             'q'         : equation,
             'section'   : section,
             's'         : section,
             'paragraph' : paragraph,
             'p'         : paragraph,
             'item'      : item,
             'i'         : item,
             'prune'     : prune,
             'u'         : prune,
             'marginnote': marginnote,
             'n'         : marginnote,

             ## here, positional parameters are files (graphics files) ##
             'figure'    : figure,
             'f'         : figure
            }


def call():
    # return words for custom tab completion
    if len(sys.argv) == 2 and sys.argv[1] == '--comp-words':
        keys = sorted(_cmd2func.keys())
        print(' '.join(keys))
        sys.exit(0)

    # to enable custom tab completion, add the following lines to your .bashrc
    # (see http://aplawrence.com/Unix/customtab.html#ixzz27bkFS2Y0):
    #lnotewords='create edit equation figure linebreak list paragraph prune
                #rename section text merge delete export view'
    #notebooks="`ls ~/data/lnote` today yesterday tomorrow"
    #_lnote()
    #{
        #local curw
        #COMPREPLY=()
        #curw=${COMP_WORDS[COMP_CWORD]}
        #cur1=${COMP_WORDS[1]}
        #if [ $COMP_CWORD == 1 ]
        #then
        #COMPREPLY=($(compgen -W '$lnotewords' -- $curw))
        #else
        #if [ "$cur1" == "figure" ] || [ "$cur1" == "f" ]
        #then
            #COMPREPLY=($(compgen -A file -- $curw))
        #elif [ "$cur1" == "create" ] || [ "$cur1" == "c" ] \
            #|| [ "$cur1" == "delete" ] || [ "$cur1" == "d" ] \
            #|| [ "$cur1" == "rename" ] || [ "$cur1" == "r" ] \
            #|| [ "$cur1" == "list" ] || [ "$cur1" == "l" ] \
            #|| [ "$cur1" == "edit" ] || [ "$cur1" == "e" ] \
            #|| [ "$cur1" == "merge" ] || [ "$cur1" == "m" ] \
            #|| [ "$cur1" == "view" ] || [ "$cur1" == "v" ] \
            #|| [ "$cur1" == "export" ] || [ "$cur1" == "x" ]
        #then
            #COMPREPLY=($(compgen -W '$notebooks' -- $curw))
        #else
            #COMPREPLY=($(compgen -W '' -- $curw))
        #fi
        #fi
        #return 0
    #}
    #complete -F _lnote -o dirnames lnote

    if len(sys.argv) == 1 or sys.argv[1] in ('-?', '--help'):
        # display help
        cmds = {}
        for cmd, func in _cmd2func.items():
            func = func.__name__
            if func not in cmds:
                cmds[func] = {'longs': [], 'shorts': []}
            if len(cmd) == 1:
                cmds[func]['shorts'].append(cmd)
            else:
                cmds[func]['longs'].append(cmd)

        keys = sorted(cmds.keys())
        cmdstrings = []
        for key in keys:
            cmd = cmds[key]
            cmdstring = ''
            if len(cmd['longs']) != 0:
                cmdstring += cmd['longs'][0]
                if len(cmd['shorts']) != 0:
                    cmdstring += ' ('
                    cmdstring += ', '.join(short for short in cmd['shorts'])
                    cmdstring += ')'
            else:
                cmdstring += ', '.join(short for short in cmd['shorts'])
            cmdstrings.append(cmdstring)

        print(__doc__)
        print()
        print('Available commands (with shortcuts):')
        printcols(cmdstrings)
        print()
        print('To get help to a specific command, use "-?", e.g. "lnote create -?"')
    else:
        # execute command
        try:
            func = _cmd2func[sys.argv[1]]
        except KeyError:
            print(f'{sys.argv[1]}: command not found. ' +
                  'Type "lnote -?" for a list of lnote commands', file=sys.stderr)
            sys.exit(1)
        func(*sys.argv[2:])
    sys.exit(0)


if __name__ == '__main__':
    call()
    sys.exit(0)
