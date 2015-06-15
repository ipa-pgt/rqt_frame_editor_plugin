#!/usr/bin/env python


## TODO: DISCLAIMER, LICENSE, STUFF,...

import time
import threading

import rospy
import rosparam

import tf

from frame_editor.objects import *
from frame_editor.commands import *

from frame_editor.constructors_geometry import *
from frame_editor.constructors_std import *

## Views
from frame_editor.interface_interactive_marker import FrameEditor_InteractiveMarker
from frame_editor.interface_services import FrameEditor_Services

from python_qt_binding import QtCore
from python_qt_binding.QtGui import QUndoStack


class FrameEditor(QtCore.QObject):

    def __init__(self):
        super(FrameEditor, self).__init__()

        self.frames = {}
        self.active_frame = None
        
        self.observers = []

        self.interactive = FrameEditor_InteractiveMarker(self)
        self.services = FrameEditor_Services(self)

        self.undo_level = 0
        self.undo_stack = QUndoStack()
        self.undo_stack.indexChanged.connect(self.undo_stack_changed)
        self.__command_lock = threading.Lock()

    @QtCore.Slot(int)
    def undo_stack_changed(self, idx):
        self.update_obsevers(self.undo_level)

    def add_undo_level(self, level):
        self.undo_level = self.undo_level | level

    def command(self, command):
        with self.__command_lock:
            self.undo_stack.push(command)


    def select_frame(self, frame):
        if self.active_frame is not frame:
            self.active_frame = frame
            self.update_obsevers(2) # update GUI


    def update_frame(self, frame):
        if frame:
            frame.broadcast() # update tf
        self.select_frame(self.active_frame) # update marker (just in case)
        time.sleep(0.1) # wait a bit for tf # TODO better way?
        self.update_obsevers(4) # update GUI


    def update_obsevers(self, level):
        for observer in self.observers:
            observer.update(self, level)
        self.undo_level = 0


    def get_tf_frames(self):
        return Frame.listener.getFrameStrings()


    def align_frame(self, frame, source_name, mode):

        (position, orientation) = frame.listener.lookupTransform(frame.parent, source_name, rospy.Time(0))

        pos = list(frame.position)
        if "x" in mode:
            pos[0] = position[0]
        if "y" in mode:
            pos[1] = position[1]
        if "z" in mode:
            pos[2] = position[2]
        frame.position = tuple(pos)

        rpy = list(tf.transformations.euler_from_quaternion(frame.orientation))
        rpy_new = tf.transformations.euler_from_quaternion(orientation)
        if "a" in mode:
            rpy[0] = rpy_new[0]
        if "b" in mode:
            rpy[1] = rpy_new[1]
        if "c" in mode:
            rpy[2] = rpy_new[2]
        if "a" in mode or "b" in mode or "c" in mode:
            frame.orientation = tf.transformations.quaternion_from_euler(*rpy)

        self.update_frame(frame)


    def broadcast(self):
        #print "> Broadcasting"
        for frame in self.frames.values():
            frame.broadcast()



    ## PRINT ##
    ##
    def print_all(self):
        print "> Printing all frames"

        for frame in self.frames:
            frame.print_all()


    ## FILE I/O ##
    ##
    def load_file(self, filename, namespace = None):
        print "> Loading file"
        data = rosparam.load_file(filename, namespace)[0][0]
        print data
        self.load_data(data)

    def load_params(self, namespace):
        if not rosparam.list_params(namespace):
            print "> No data to load"
        else:
            data = rosparam.get_param(namespace)
            self.load_data(data)

    def load_data(self, data):

        ## Import data
        for name, frame in data["frames"].items():
            t = frame["position"]
            o = frame["orientation"]

            if "style" in frame:
                style = frame["style"]
            else:
                style = "none"

            if "data" in frame:
                dat = frame["data"]

            position = (t["x"], t["y"], t["z"])
            orientation = (o["x"], o["y"], o["z"], o["w"])

            if style == "plane":
                f = Object_Plane(name, position, orientation, frame["parent"], dat["length"], dat["width"])
            elif style == "cube":
                f = Object_Cube(name, position, orientation, frame["parent"], dat["length"], dat["width"], dat["height"])
            elif style == "sphere":
                f = Object_Sphere(name, position, orientation, frame["parent"], dat["diameter"])
            elif style == "axis":
                f = Object_Axis(name, position, orientation, frame["parent"], dat["length"], dat["width"])
            else:
                f = Frame(name, position, orientation, frame["parent"])
            
            self.command(Command_AddElement(self, f))

        print "> Loading done"

    def save_file(self, filename, namespace):

        ## Data
        data = {}
        frames = {}

        for frame in self.frames.values():
            t = {}
            t["x"] = frame.position[0]
            t["y"] = frame.position[1]
            t["z"] = frame.position[2]

            o = {}
            o["x"] = frame.orientation[0]
            o["y"] = frame.orientation[1]
            o["z"] = frame.orientation[2]
            o["w"] = frame.orientation[3]

            f = {}
            f["parent"] = frame.parent
            f["position"] = t
            f["orientation"] = o

            f["style"] = frame.style

            if frame.style == "plane":
                f["data"] = { "length": frame.length, "width":frame.width }
            
            elif frame.style == "cube":
                f["data"] = { "length": frame.length, "width": frame.width, "height": frame.height }
            
            elif frame.style == "sphere":
                f["data"] = { "diameter": frame.diameter }
            
            elif frame.style == "axis":
                f["data"] = { "length": frame.length, "width": frame.width }

            frames[frame.name] = f

        data["frames"] = frames

        ## To parameter server
        rospy.set_param(namespace, data)
        print rospy.get_param(namespace)

        ## Dump param to file
        print "Saving to file", filename
        rosparam.dump_params(filename, namespace)
        print "Saving done"


if __name__ == "__main__":

    rospy.init_node('frame_editor')

    editor = FrameEditor()
    editor.load_params(rospy.get_name())

    print "Frame editor ready!"
    rate = rospy.Rate(100) # hz
    while not rospy.is_shutdown():
        editor.broadcast()
        rate.sleep()

# eof
