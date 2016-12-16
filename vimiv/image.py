#!/usr/bin/env python
# encoding: utf-8
"""Image part of vimiv."""

import os
from random import shuffle
from gi import require_version
require_version('Gtk', '3.0')
from gi.repository import Gtk, GdkPixbuf, GLib


class Image(object):
    """Image class for vimiv.

    Includes the scrollable window with the image and all actions that apply
    to it.

    Attributes:
        app: The main vimiv class to interact with.
        scrolled_win: Gtk.ScrollableWindow for the image.
        viewport: Gtk.Viewport to be able to scroll the image.
        image: Gtk.Image containing the actual image Pixbuf.
        animation_toggled: If True play animations.
        user_zoomed: If True do not rezoom automatically.
        trashdir: Directory for all the deleted files.
        overzoom: If True, increase image size up to window size even if images
            are smaller than window.
        rescale_svg: If True rescale vector graphics when zooming.
        shuffle: If True randomly shuffle paths.
        zoom_percent: Percentage to zoom to compared to the original size.
        imsize: Size of the displayed image as a tuple.
        pixbuf_original: Original image.
        pixbuf_iter: Iter of displayed animation.
        timer_id: Id of current animation timer.
    """

    def __init__(self, app, settings):
        """Set default values for attributes."""
        self.app = app
        general = settings["GENERAL"]

        # Generate window structure
        # Scrollable window for the image
        self.scrolled_win = Gtk.ScrolledWindow()
        self.scrolled_win.set_hexpand(True)
        self.scrolled_win.set_vexpand(True)

        # Viewport
        self.viewport = Gtk.Viewport()
        self.image = Gtk.Image()
        self.scrolled_win.add(self.viewport)
        self.viewport.add(self.image)
        self.scrolled_win.connect("key_press_event", self.app["keyhandler"].run,
                                  "IMAGE")

        # Settings
        self.animation_toggled = False
        self.user_zoomed = False  # checks if the user manually zoomed the image
        self.trashdir = os.path.join(self.app.directory, "Trash")
        self.overzoom = general["overzoom"]
        self.rescale_svg = general["rescale_svg"]
        self.shuffle = general["shuffle"]
        self.zoom_percent = 1
        self.imsize = [0, 0]
        self.pixbuf_original = GdkPixbuf.PixbufAnimation
        self.pixbuf_iter = GdkPixbuf.PixbufAnimationIter
        self.timer_id = 0

    def check_for_edit(self, force):
        """Check if an image was edited before moving.

        Args:
            force: If True move and ignore any editing.
        Return:
            0 if no edits were done or force, 1 else.
        """
        if self.app.paths and "EDIT" in self.app.paths[self.app.index] \
                and not force:
            self.app["statusbar"].err_message(
                "Image has been edited, add ! to force")
            return 1
        return 0

    def get_zoom_percent_to_fit(self, z_width=False, z_height=False):
        """Get the zoom factor perfectly fitting the image to the window.

        Args:
            z_width: If True zoom to width.
            z_height: If True zoom to height.
        Return:
            Zoom percentage.
        """
        # Size of the file
        pbo_width = self.pixbuf_original.get_width()
        pbo_height = self.pixbuf_original.get_height()
        pbo_scale = pbo_width / pbo_height
        # Size of the image to be shown
        w_scale = self.imsize[0] / self.imsize[1]
        stickout = z_width | z_height

        # Image is completely shown and user doesn't want overzoom
        if (pbo_width < self.imsize[0] and pbo_height < self.imsize[1] and
                not (stickout or self.overzoom)):
            return 1
        # "Portrait" image
        elif (pbo_scale < w_scale and not stickout) or z_height:
            return self.imsize[1] / pbo_height
        # "Panorama/landscape" image
        else:
            return self.imsize[0] / pbo_width

    def update(self, update_info=True, update_gif=True):
        """Show the final image.

        Args:
            update_info: If True update the statusbar with new information.
            update_gif: If True update animation status.
        """
        if not self.app.paths:
            return
        pbo_width = self.pixbuf_original.get_width()
        pbo_height = self.pixbuf_original.get_height()

        # pylint:disable=no-member
        try:  # Try to scale the image
            pbf_width = int(pbo_width * self.zoom_percent)
            pbf_height = int(pbo_height * self.zoom_percent)
            # Rescaling of svg
            name = self.app.paths[self.app.index]
            info = GdkPixbuf.Pixbuf.get_file_info(name)[0]
            if "svg" in info.get_extensions():
                pixbuf_final = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                    self.app.paths[self.app.index], -1, pbf_height, True)
            else:
                pixbuf_final = self.pixbuf_original.scale_simple(
                    pbf_width, pbf_height, GdkPixbuf.InterpType.BILINEAR)
            self.image.set_from_pixbuf(pixbuf_final)
        except:  # If that does not work it must be an animation
            self.zoom_percent = 1
            if update_gif:
                if not self.animation_toggled:
                    delay = self.pixbuf_iter.get_delay_time()
                    self.timer_id = GLib.timeout_add(delay, self.play_gif)
                    self.play_gif()
                else:
                    self.pause_gif()
        # Update the statusbar if required
        if update_info:
            self.app["statusbar"].update_info()

    def play_gif(self):
        """Run the animation of a gif."""
        image = self.pixbuf_iter.get_pixbuf()
        self.image.set_from_pixbuf(image)
        if self.pixbuf_iter.advance():
            GLib.source_remove(self.timer_id)
            delay = self.pixbuf_iter.get_delay_time()
            self.timer_id = GLib.timeout_add(delay, self.play_gif)

    def pause_gif(self):
        """Pause a gif or show initial image."""
        if self.timer_id:
            GLib.source_remove(self.timer_id)
            self.timer_id = 0
        else:
            image = self.pixbuf_iter.get_pixbuf()
            self.image.set_from_pixbuf(image)

    def get_available_size(self):
        """Receive size not occupied by other Widgets.

        Substracts other widgets (manipulate, statusbar, library) from window
        size and returns the available size.

        Return:
            Tuple of available size.
        """
        size = self.app["window"].get_size()
        if self.app["library"].grid.is_visible():
            size = (size[0] - self.app["library"].width, size[1])
        if not self.app["statusbar"].hidden:
            size = (size[0], size[1]
                    - self.app["statusbar"].separator.get_margin_top() - 2)
        return size

    def zoom_delta(self, delta):
        """Zoom the image by delta percent.

        Args:
            delta: Percentage to change zoom by.
        """
        if self.app["thumbnail"].toggled:
            return
        try:
            self.zoom_percent = self.zoom_percent * (1 + delta)
            # Catch some unreasonable zooms
            if (self.pixbuf_original.get_height() * self.zoom_percent < 50 or
                    self.pixbuf_original.get_height() * self.zoom_percent >
                    self.app["window"].get_size()[0] * 5):
                raise ValueError
            self.user_zoomed = True
            self.update(update_gif=False)
        except:
            self.zoom_percent = self.zoom_percent / (1 + delta)
            message = "Warning: Object cannot be zoomed (further)"
            self.app["statusbar"].err_message(message)

    def zoom_to(self, percent, z_width=False, z_height=False):
        """Zoom to a given percentage.

        Args:
            percent: Percentage to zoom to.
            z_width: If True zoom to width.
            z_height: If True zoom to height.
        """
        if self.app["thumbnail"].toggled:
            return
        before = self.zoom_percent
        self.user_zoomed = False
        # Catch user zooms
        if self.app["keyhandler"].num_str:
            self.user_zoomed = True
            percent = self.app["keyhandler"].num_str
            # If prefixed with a zero invert value
            try:
                if percent[0] == "0":
                    percent = 1 / float(percent[1:])
                else:
                    percent = float(percent)
            except:
                self.app["statusbar"].err_message(
                    "Error: Zoom percentage not parseable")
                return
            self.app["keyhandler"].num_str = ""
        try:
            self.imsize = self.get_available_size()
            self.zoom_percent = (percent if percent
                                 else self.get_zoom_percent_to_fit(z_width, z_height))
            # Catch some unreasonable zooms
            if (self.pixbuf_original.get_height() * self.zoom_percent < 5 or
                    self.pixbuf_original.get_height() * self.zoom_percent >
                    self.app["window"].get_size()[0] * 5):
                self.zoom_percent = before
                raise ValueError
            self.update(update_gif=False)
        except:
            self.app["statusbar"].err_message(
                "Warning: Object cannot be zoomed (further)")

    def center_window(self):
        """Center the image in the current window."""
        # Don't do anything if no images are open
        if not self.app.paths or self.app["thumbnail"].toggled:
            return
        # Get center of adjustments and set them
        h_adj = Gtk.Scrollable.get_hadjustment(self.viewport)
        h_middle = (h_adj.get_upper() - h_adj.get_lower() - self.imsize[0]) / 2
        h_adj.set_value(h_middle)
        v_adj = Gtk.Scrollable.get_vadjustment(self.viewport)
        v_middle = (v_adj.get_upper() - v_adj.get_lower() - self.imsize[1]) / 2
        v_adj.set_value(v_middle)
        Gtk.Scrollable.set_hadjustment(self.viewport, h_adj)
        Gtk.Scrollable.set_vadjustment(self.viewport, v_adj)

    def move_index(self, forward=True, key=None, delta=1, force=False):
        """Move by delta in paths.

        Args:
            forward: If True move forwards. Else move backwards.
            key: If available, move by key.
            delta: Positions to move by.
            force: If True, move regardless of editing image.
        """
        # Check if an image is opened or if it has been edited
        if not self.app.paths or self.app["thumbnail"].toggled or \
                self.check_for_edit(force):
            return
        # Check for prepended numbers and direction
        if key and self.app["keyhandler"].num_str:
            delta *= int(self.app["keyhandler"].num_str)
        if not forward:
            delta *= -1

        self.app.index = (self.app.index + delta) % len(self.app.paths)
        self.user_zoomed = False

        # Reshuffle on wrap-around
        if self.shuffle and self.app.index is 0 and delta > 0:
            shuffle(self.app.paths)

        path = self.app.paths[self.app.index]
        # Show the image at path and receive possible errors
        returncode = self.show_image(path, delta is not 0)

        # Info if slideshow returns to beginning
        if self.app["slideshow"].running and not returncode:
            if self.app.index is self.app["slideshow"].start_index:
                message = "Info: back at beginning of slideshow"
                self.app["statusbar"].lock = True
                self.app["statusbar"].err_message(message)
            else:
                self.app["statusbar"].lock = False

        self.app["keyhandler"].num_clear()
        return True  # for the slideshow

    def show_image(self, path, update_image=True):
        """Show the image at position path.

        Check for inexistent and inaccessible files.

        Args:
            path: The path in self.app.paths to operate on.
        Return:
            errorcode: 1 if there are errors, 0 else.
        """
        errorcode = 0
        try:
            if not os.path.exists(path):
                self.app["manipulate"].delete()
                errorcode = 1
            else:
                self.pixbuf_original = GdkPixbuf.PixbufAnimation.new_from_file(
                    path)
            if self.pixbuf_original.is_static_image():
                self.pixbuf_original = self.pixbuf_original.get_static_image()
                self.imsize = self.get_available_size()
                self.zoom_percent = self.get_zoom_percent_to_fit()
            else:
                self.pixbuf_iter = self.pixbuf_original.get_iter()
                self.zoom_percent = 1
            # If there was a running gif, remove the timer
            if self.timer_id:
                self.pause_gif()
            # If one simply reloads the file the info shouldn't be updated
            self.update(update_image)
        # File not accessible
        except GLib.Error:
            self.app.paths.remove(path)
            self.app["statusbar"].err_message("Error: file not accessible")
            self.move_pos(False)
            errorcode = 1
        return errorcode

    def move_pos(self, forward=True, force=False):
        """Move to specific position in paths.

        Args:
            forward: If True move forwards. Else move backwards.
            force: If True, move regardless of editing image.
        """
        # Check if image has been edited (might be gone by now -> try)
        try:
            if self.check_for_edit(force):
                raise ValueError
        except:
            return
        max_pos = len(self.app.paths)
        current = self.app.get_pos(force_widget="im")
        # Move to definition by keys or end/beg
        if self.app["keyhandler"].num_str:
            pos = int(self.app["keyhandler"].num_str)
        elif forward:
            pos = max_pos
        else:
            pos = 1
        # Catch exceptions
        try:
            current = int(current)
            max_pos = int(max_pos)
            if pos < 0 or pos > max_pos:
                raise ValueError
        except:
            self.app["statusbar"].err_message("Warning: Unsupported index")
            return False
        # Do the maths and move
        dif = pos - current - 1
        if self.app["thumbnail"].toggled:
            pos -= 1
            self.app["thumbnail"].move_to_pos(pos)
        else:
            self.move_index(True, False, dif)
            self.user_zoomed = False

        self.app["keyhandler"].num_clear()
        return True

    def toggle_rescale_svg(self):
        """Toggle rescale state of vector images."""
        self.rescale_svg = not self.rescale_svg

    def toggle_overzoom(self):
        """Toggle overzoom of images."""
        self.overzoom = not self.overzoom

    def toggle_animation(self):
        """Toggle animation status of Gifs."""
        if self.app.paths and not self.app["thumbnail"].toggled:
            self.animation_toggled = not self.animation_toggled
            self.update()
