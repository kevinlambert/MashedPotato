#!/usr/bin/env python2
from __future__ import with_statement

import os
import sys
import time
import datetime
import re
import subprocess

"""MashedPotato: An automatic JavaScript and CSS minifier

A monitor tool which checks JS and CSS files every second and
reminifies them if they've changed. Just leave it running, monitoring
your directories.

Specify a .mash file in your root directory to tell MashedPotato which
directories to monitor. See .mash_example for an example.

Usage example:

$ ./mashed_potato.py /home/wilfred/work/gxbo

To run the tests:

$ ./tests

"""

# paths/error times of files we failed to minify
error_files = {}

class MinifyFailed(Exception): pass


def get_paths_from_configuration(project_path, configuration_file):
    """Given a the contents of a configuration file, return a list of
    regular expressions that match absolute paths according to that
    configuration.
    
    """
    current_State = ""
    
    config = {'monitor_path_regexps': [], 'write_path_regexps': []}

    
    for (line_number, line) in enumerate(configuration_file.split('\n')):
        line = line.strip()

        if line and not line.startswith('#'):
            if line.endswith('/'):
                print("Warning: directory regexps must not end with '/'. "
                      "Line %d will not do anything." % (line_number + 1))
                                                      # lines are zero-indexed
            else:
                if line.startswith('[WATCH]'):
                    current_State = '[WATCH]'
                    continue
                elif line.startswith('[WRITE]'):
                    current_State = '[WRITE]'
                    continue
                
                if current_State == '[WATCH]' :
                    config['monitor_path_regexps'].append(get_path_regexp(project_path, line))
                elif current_State == '[WRITE]' :
                    config['write_path_regexps'].append(os.path.join(project_path, line))
                else:
                    path_regexps.append(get_path_regexp(project_path, line))

    return config


def get_path_regexp(project_path, relative_regexp):
    """Convert a path regexp accepted by mashed_potato to a regular
    expression which matches an absolute path.

    >>> get_path_regexp("/home/wilfred/gxbo", "foo/{a,b}")
    ^/home/wilfred/gxbo/foo/{a,b}$
    
    """
    absolute_regexp = os.path.join(project_path, relative_regexp)

    return "^%s$" % absolute_regexp


def path_matches_regexps(path, path_regexps):
    """Test whether this path matches any of the given regular expressions.
    
    """
    for regexp in path_regexps:
        if re.match(regexp, path):
            return True

    return False

def is_minifiable(file_path):
    """JS or CSS files that aren't minified or hidden.

    """
    directory_path, file_name = os.path.split(file_path)
    
    if file_name.startswith('.'):
        return False

    if not (file_name.endswith('.js') or file_name.endswith('.css')):
        return False

    if file_name.endswith('.min.js') or file_name.endswith('.min.css'):
        return False

    return True

def get_minified_name(file_path):
    """Convert a file name into its minified version. We don't do a
    simple .replace() to avoid corner cases, as shown in the example.

    >>> get_minified_name("/a/b/.js/c/foo.js)
    "/a/b/.js/c/foo.min.js"

    """
    if file_path.endswith('.js'):
        minified_path = file_path[:-3] + '.min.js'
    elif file_path.endswith('.css'):
        minified_path = file_path[:-4] + '.min.css'

    return minified_path


def needs_minifying(file_path):
    """Returns false if a file already has a minified file, and the
    minified file is newer than the source. We return false on files
    that errored last time and haven't changed since.

    """
    source_edited_time = os.path.getmtime(file_path)

    last_minified_time = None
    minified_file_path = get_minified_name(file_path)

    if os.path.exists(minified_file_path):
        last_minified_time = os.path.getmtime(minified_file_path)

    # don't minify if it is already minified and hasn't changed since
    if last_minified_time and last_minified_time > source_edited_time:
        return False

    # don't attempt to minify if there was an error last time and it
    # hasn't changed since
    if file_path in error_files and error_files[file_path] > source_edited_time:
        return False

    return True

def is_uglifyjs_installed():
    """Is uglifyjs installed and on PATH?

    If you want it installed:
    $ npm install uglify-js

    """
    for path in os.environ["PATH"].split(os.pathsep):
        full_path = os.path.join(path, "uglifyjs")

        if os.path.exists(full_path):
            return True

    return False

def is_juicer_installed():
    """Is juicer installed and on PATH?

    If you want it installed:
    $ gem install juicer
    $ juicer install yui_compressor
    $ juicer install closure_compiler
    $ juicer install jslint

    """
    for path in os.environ["PATH"].split(os.pathsep):
        full_path = os.path.join(path, "juicer")

        if os.path.exists(full_path):
            return True

    return False

def minify(file_path):
    """Create a minified JS or CSS file of the file at file_path.

    For JS we use uglifyjs if it's available, since the compression is
    better. CSS always uses YUICompressor.

    """
    if is_juicer_installed():
        command_line = "juicer merge %s" % \
            (file_path)
    
    elif file_path.endswith(".js") and is_uglifyjs_installed():
        # strip comments at the start:
        command_line = "uglifyjs -nc %s > %s" % \
            (file_path, get_minified_name(file_path))
    else:
        mashed_potato_path = os.path.dirname(os.path.abspath(__file__))
        command_line ='java -jar %s/yuicompressor-2.4.5.jar %s > %s' % \
            (mashed_potato_path, file_path, get_minified_name(file_path))

    try:
        p = subprocess.Popen(command_line, shell=True, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, close_fds=True)
    except OSError, e:
        print "\nAn error occured running\n%s\n" % command_line
        print e.strerror
        sys.exit()

    error = p.stderr.read()
    if error:
        raise MinifyFailed()


def update_error_logs(errored, path):
    """Write a list of files that aren't minifying into a file called
    MASH_ERRORS in the project dir.

    If nothing has errored, remove the file entirely.

    """
    if errored:
        error_files[path] = time.time()
    else:
        # the file is good so remove it from the errored file list
        if path in error_files:
            del error_files[path]

    # update MASH_ERRORS so it records the files that are currently erroring
    error_file_path = os.path.join(project_path, 'MASH_ERRORS')

    if error_files:
        with open(error_file_path, 'wb') as error_log:
            for file_path in error_files.keys():
                error_log.write('%s\n' % file_path)

    else:
        if os.path.exists(error_file_path):
            os.remove(error_file_path)


def all_monitored_files(path_regexps, project_path):
    """For all the subdirectories in this path which match a
    path_regexp, return a list of their files and paths.

    """
    assert os.path.isabs(project_path), "project_path should be absolute"
    
    for subdirectory_path, subdirectories, files in os.walk(project_path):
        if path_matches_regexps(subdirectory_path, path_regexps):

            # this directory matches, so yield all its contents
            for file_name in files:
                file_path = os.path.join(subdirectory_path, file_name)
                yield file_path


def continually_monitor_files(config, project_path):
    while True:
        for file_path in all_monitored_files(config['monitor_path_regexps'], project_path):
            if is_minifiable(file_path) and needs_minifying(file_path):
                try:
                    if is_juicer_installed():
                        for write_file in config['write_path_regexps']:
                            minify(write_file)
                        
                        break
                        
                    else:
                        minify(file_path)
                        
                    # inform the user:
                    now_time = datetime.datetime.now().time()
                    pretty_now_time = str(now_time).split('.')[0]
                    print "[%s] Minified %s" % (pretty_now_time, file_path)

                    update_error_logs(False, file_path)

                except MinifyFailed:
                    print "Error minifying %s" % file_path
                    update_error_logs(True, file_path)
                        
        time.sleep(1)


if __name__ == '__main__':
    try:
        project_path = sys.argv[1]
        project_path = os.path.abspath(project_path)
        configuration_path = os.path.join(project_path, ".mash")
    except IndexError:
        print "Usage: ./mashed_potato <directory containing .mash file>"
        sys.exit()

    if os.path.exists(configuration_path):
        configuration_file = open(configuration_path, 'r').read()
        config = get_paths_from_configuration(project_path, configuration_file)

    else:
        print "There isn't a .mash file at \"%s\"." % os.path.abspath(project_path)
        print "Look at .mash_example in %s for an example." % os.path.abspath(os.path.dirname(__file__))
        sys.exit()

    print "Monitoring JavaScript and CSS files for changes."
    print "Press Ctrl-C to quit or Ctrl-Z to stop."
    print ""

    try:
        continually_monitor_files(config, project_path)
    except KeyboardInterrupt:
        print "" # for tidyness' sake

