# vim: ft=python fileencoding=utf-8 sw=4 et sts=4
"""Different actions applying directly to files."""

import os
from random import shuffle

from gi.repository import Gdk, GdkPixbuf, Gtk
from vimiv.helpers import listdir_wrapper
from vimiv.settings import settings

# We need the try ... except wrapper here
# pylint: disable=ungrouped-imports
try:
    from gi.repository import GExiv2
    _has_exif = True
except ImportError:
    _has_exif = False


def recursive_search(directory):
    """Search a directory recursively for images.

    Args:
        directory: Directory to search for images.
    Return:
        List of images in directory.
    """
    for root, _, files in os.walk(directory):
        for fil in files:
            yield os.path.join(root, fil)


def populate_single(arg, recursive):
    """Populate a complete filelist if only one path is given.

    Args:
        arg: Single path given.
        recursive: If True search path recursively for images.
    Return:
        Generated list of paths.
    """
    paths = []
    if os.path.isfile(arg):
        # Use parent directory
        directory = os.path.dirname(arg)
        if not directory:  # Default to current directory
            directory = "./"
        paths = listdir_wrapper(directory)
        paths = [os.path.join(directory, path) for path in paths]
        # Set the argument to the beginning of the list
    elif os.path.isdir(arg) and recursive:
        paths = sorted(recursive_search(arg))
    return paths


def populate(args, recursive=False, shuffle_paths=False, expand_single=True):
    """Populate a list of files out given paths.

    Args:
        args: Paths given.
        recursive: If True search path recursively for images.
        shuffle_paths: If True shuffle found paths randomly.
        expand_single: If True, populate a complete filelist with images from
            the same directory as the single argument given.
    Return:
        Found paths, position of first given path.
    """
    paths = []
    index = 0
    # If only one path is passed do special stuff
    first_path = os.path.abspath(args[0]) if args else None
    if len(args) == 1 and expand_single:
        args = populate_single(first_path, recursive)

    # Add everything
    for arg in args:
        path = os.path.abspath(arg)
        if os.path.isfile(path):
            paths.append(path)
        elif os.path.isdir(path) and recursive:
            paths = list(recursive_search(path))
    # Remove unsupported files
    paths = [possible_path for possible_path in paths
             if is_image(possible_path)]
    index = paths.index(first_path) if first_path in paths else 0

    # Shuffle
    if shuffle_paths:
        shuffle(paths)

    return paths, index


def is_image(filename):
    """Check whether a file is an image.

    Args:
        filename: Name of file to check.
    """
    try:
        complete_name = os.path.abspath(os.path.expanduser(filename))
        return bool(GdkPixbuf.Pixbuf.get_file_info(complete_name)[0])
    except UnicodeEncodeError:
        return False


def is_animation(filename):
    """Check whether a file is an animated image.

    Args:
        filename: Name of file to check.
    """
    complete_name = os.path.abspath(os.path.expanduser(filename))
    info = GdkPixbuf.Pixbuf.get_file_info(complete_name)[0]
    if not info:
        return False
    return "gif" in info.get_extensions()


def is_svg(filename):
    """Check whether a file is a vector graphic.

    Args:
        filename: Name of file to check.
    """
    complete_name = os.path.abspath(os.path.expanduser(filename))
    info = GdkPixbuf.Pixbuf.get_file_info(complete_name)[0]
    return "svg" in info.get_extensions() if info else False


def edit_supported(filename):
    """Check whether a file is editable for vimiv.

    Args:
        filename: Name of file to check.
    """
    complete_name = os.path.abspath(os.path.expanduser(filename))
    info = GdkPixbuf.Pixbuf.get_file_info(complete_name)[0]
    extension = info.get_extensions()[0]
    if extension in ["jpeg", "png", "tiff", "ico", "bmp"]:
        return True
    return False


def format_files(app, string):
    """Format image names in filelist according to a formatstring.

    Numbers files in form of formatstring_000.extension. Replaces exif
    information accordingly.

    Args:
        app: Vimiv application to interact with.
        string: Formatstring to use.
    """
    # Catch problems
    if app["library"].is_focus():
        message = "Format only works on opened image files"
        app["statusbar"].message(message, "info")
        return
    if not app.get_paths():
        app["statusbar"].message("No files in path", "info")
        return

    # Check if exif data is available and needed
    tofind = ("%" in string)
    if tofind:
        if not _has_exif:
            app["statusbar"].message(
                "Install gexiv2 for EXIF support in vimiv", "error")
            return
        for fil in app.get_paths():
            exif = GExiv2.Metadata(fil)
            try:
                exif.get_date_time()
            except KeyError:
                app["statusbar"].message(
                    "No exif data for %s available" % (fil), "error")
                return

    for i, fil in enumerate(app.get_paths()):
        ending = os.path.splitext(fil)[1]
        num = "%03d" % (i + 1)
        # Exif stuff
        if tofind:
            exif = GExiv2.Metadata(fil)
            date = exif.get_date_time()
            outstring = string.replace("%Y", str(date.year))
            outstring = outstring.replace("%m", str(date.month))
            outstring = outstring.replace("%d", str(date.day))
            outstring = outstring.replace("%H", str(date.hour))
            outstring = outstring.replace("%M", str(date.minute))
            outstring = outstring.replace("%S", str(date.second))
        else:
            outstring = string
        # Ending
        outstring += num + ending
        os.rename(fil, outstring)

    app.emit("paths-changed", format_files)


class ClipboardHandler(object):
    """Deals with copying to the system clipboard."""

    def __init__(self, app):
        """Receive and set main vimiv application.

        Args:
            _app: The main vimiv class to interact with.
        """
        self._app = app

    def copy_name(self, abspath=False):
        """Copy image name to clipboard.

        Args:
            abspath: Use absolute path or only the basename.
        """
        # Get name to copy
        name = self._app.get_pos(True)
        if abspath:
            name = os.path.abspath(name)
        else:
            name = os.path.basename(name)
        # Set clipboard
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_PRIMARY) \
            if settings["copy_to_primary"].get_value() \
            else Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        # Text to clipboard
        clipboard.set_text(name, -1)
        # Info message
        message = "Copied <b>" + name + "</b> to %s" % \
            ("primary" if settings["copy_to_primary"].get_value()
             else "clipboard")
        self._app["statusbar"].message(message, "info")
