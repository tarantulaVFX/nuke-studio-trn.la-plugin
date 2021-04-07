# --------------------------Trn.la Plugin For Nuke Studio--------------------------------
# Subclass of ShotProcessor that can export shots from NukeStudio sequences and upload
# to trn.la.
# 
# (c) 2021 Tarantula
# Author: Moses Molina
# ---------------------------------------------------------------------------------------
import os
import json
import os.path as path
import nuke

import hiero.core

from hiero.exporters import FnShotProcessor
from hiero.exporters.FnExportKeywords import kFileBaseKeyword, kFileHeadKeyword, kFilePathKeyword, KeywordTooltips
from hiero.exporters.FnExternalRender import getRoleFromProperty, getColorspaceFromProperty, _mapDefaultColourTransform
import hiero.core.FnNukeHelpers as FnNukeHelpers

from PySide2 import (QtCore, QtGui, QtWidgets, QtNetwork)
from PySide2.QtGui import *
from PySide2.QtCore import *
from PySide2.QtWidgets import *
from PySide2.QtNetwork import *

try:
    from hiero.exporters.FnShotProcessorUI import ShotProcessorUI
except ImportError:
    ShotProcessorUI = FnShotProcessor.ShotProcessor

from .TrnlaTranscodeExporter import TrnlaTranscodeExporter
from .TrnlaPreviewTranscoder import TrnlaPreviewTranscoder, TrnlaPreviewTranscoderPreset

from .TrnlaLoginDialog import TrnlaLoginDialog


class TrnlaShotProcessorUI(ShotProcessorUI):
    def __init__(self, preset):
        ShotProcessorUI.__init__(self, preset)

    def get_api_key(self):
        TarantulaData = os.path.expanduser("~") + '/AppData/Local/Tarantula/'
        configJsonFile = TarantulaData + 'config.json'
        try:
            jsonFile = open(configJsonFile)
        except Exception as err:
            jsonFile = None
            print("No trn.la account detected. Please log in to your trn.la account on this device.")

        if jsonFile:
            config = json.load(jsonFile)
            settings = config['settings']
            return settings["api_key"]
        else:
            return None

    def displayName(self):
        return "Process as Shots for Trn.la"

    def toolTip(self):
        return "Process as Shots for Trn.la can render full quality shots and upload them to your Trn.la account."

    def onNewProjectChecked(self, state):
        if state == 0:
            self.prjNameEdit.hide()
            self.prjSelect.show()
            self.existProject.setCheckState(Qt.Checked)
            self.preset().properties()["trnla_exist_project"] = True
            self.preset().properties()["trnla_new_project"] = False
        elif state == 2:
            self.prjSelect.hide()
            self.prjNameEdit.show()
            self.existProject.setCheckState(Qt.Unchecked)
            self.preset().properties()["trnla_exist_project"] = False
            self.preset().properties()["trnla_new_project"] = True

    def onExistProjectChecked(self, state):
        if state == 0:
            self.prjSelect.hide()
            self.prjNameEdit.show()
            self.newProject.setCheckState(Qt.Checked)
            self.preset().properties()["trnla_exist_project"] = False
            self.preset().properties()["trnla_new_project"] = True
        elif state == 2:
            self.prjNameEdit.hide()
            self.prjSelect.show()
            self.newProject.setCheckState(Qt.Unchecked)
            self.preset().properties()["trnla_exist_project"] = True
            self.preset().properties()["trnla_new_project"] = False

    def onUploadFullChecked(self, state):
        if state == 0:
            self.preset().properties()["trnla_upload"] = False
        elif state == 2:
            self.preset().properties()["trnla_upload"] = True

    def get_proj_id(self, projName):
        project_ids = self.preset().properties()["trnla_project_ids"]
        project_names = self.preset().properties()["trnla_project_names"]
        for i in range(len(project_names)):
            if project_names[i] == projName:
                return project_ids[i]

    def onProjectSelected(self, projName):
        self.preset().properties()["trnla_project_name"] = projName
        self.preset().properties()["trnla_project_id"] = self.get_proj_id(projName)

    def readyRead(self, reply):
        er = reply.error()

        if er == QNetworkReply.NoError:
            bytes_string = reply.readAll()
            string1 = str(bytes_string).decode('utf8')
            replyJson = json.loads(string1)
            projectsJson = replyJson.get('projects')
            self.prjSelect.clear()
            del self.preset().properties()["trnla_project_names"][:]
            del self.preset().properties()["trnla_project_ids"][:]
            self.preset().properties()["trnla_project_name"] = ""
            self.preset().properties()["trnla_project_id"] = ""
            if projectsJson:
                for project in projectsJson:
                    self.preset().properties()["trnla_project_names"].append(project["project_name"].encode('ascii'))
                    self.preset().properties()["trnla_project_ids"].append(project["project_id"])
                    self.prjSelect.addItem(str(project['project_name']))

                self.preset().properties()["trnla_project_name"] = self.prjSelect.currentText()
                self.preset().properties()["trnla_project_id"] = self.get_proj_id(self.prjSelect.currentText())
            else:
                print('Trnla: Did not find any projects.')

        else:
            print("Error occurred: ", er)
            print(reply.errorString())

    def showLogin(self, widget):
        self.loginDlg = TrnlaLoginDialog(widget)
        if self.loginDlg.exec_():
            print('logged in!')
            self.loggedInMode(onStart=False)
        else:
            pass

    def validate(self, exportItems):
        if self.newProject.isChecked() and self.uploadFull.isChecked():
            if self.prjNameEdit.text() == '':
                nuke.message('trnla project name cannot be empty')
                return False
            else:
                self.preset().properties()["trnla_project_name"] = self.prjNameEdit.text()
                self.preset().properties()["trnla_project_id"] = False
        return ShotProcessorUI.validate(self, exportItems)

    def populateUI(self, *args, **kwargs):
        (widget, taskUIWidget, exportItems) = args

        self.api_key = self.get_api_key()
        main_layout = QtWidgets.QVBoxLayout(widget)
        main_layout.setContentsMargins(0, 0, 0, 0)

        default = QtWidgets.QWidget()
        main_layout.addWidget(default)

        # Call Base Function
        ShotProcessorUI.populateUI(self, default, taskUIWidget, exportItems)

        self.trnla_layout = QVBoxLayout(widget)
        self.sectionFont = QFont("Tahoma", 14, QFont.Bold)

        # LOGO
        logo_png = path.abspath(path.dirname(path.relpath(__file__)).replace('\\', '/') + "/tarantula.png").replace('\\', '/')
        if logo_png:
            logo = QPixmap(logo_png)
        else:
            logo = QPixmap()
        self.logoLabel = QLabel(widget)
        self.logoLabel.setPixmap(logo.scaled(100, 50, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.line = QFrame(widget)
        self.line.setFrameShape(QFrame.HLine)
        self.line.setFrameShadow(QFrame.Sunken)
        self.trnla_layout.addWidget(self.line)
        self.trnla_layout.addWidget(self.logoLabel)

        # Begin Make Rest of UI-------------------------------
        self.newProject = QCheckBox("New Project", widget)
        self.existProject = QCheckBox("Existing Project", widget)
        self.projectModesHBox = QHBoxLayout(widget)
        self.prjSelect = QComboBox(widget)
        self.prjNameEdit = QLineEdit(widget)
        self.prjSetupLayout = QVBoxLayout(widget)

        self.logout = QHBoxLayout()
        self.logoutBtn = QPushButton('Log Out')
        self.logoutBtn.clicked.connect(self.onLogOut)
        self.logout.addWidget(self.logoutBtn)
        self.logout.addStretch()

        self.message = QLabel("<b><font color=\"#ff3030\">Not logged into Trn.la on this machine.</font></b>", widget)
        self.loginBtn = QPushButton('login')
        self.loginBtn.clicked.connect(lambda: self.showLogin(widget))
        self.login = QHBoxLayout()
        self.login.addWidget(self.loginBtn)
        self.login.addStretch()
        self.trnla_layout.addWidget(self.message)
        self.trnla_layout.addLayout(self.login)

        self.newProject.stateChanged.connect(self.onNewProjectChecked)
        self.existProject.stateChanged.connect(self.onExistProjectChecked)

        self.projectModesHBox.addWidget(self.newProject)
        self.projectModesHBox.addWidget(self.existProject)
        self.projectModesHBox.addStretch()

        # PROJECT NAME
        self.prjNameLabel = QLabel('project', widget)
        self.prjNameLabel.setFont(self.sectionFont)

        self.prjNameEdit.setPlaceholderText("enter a new project name")

        # PROJECT LIST
        self.prjSelect.setEditable(False)
        self.prjSelect.hide()
        self.prjSelect.currentTextChanged.connect(self.onProjectSelected)

        self.nam = QNetworkAccessManager()
        self.nam.finished.connect(self.readyRead)
        if self.api_key:
            self.requestProjects()

        # PROJECT SETUP LAYOUT
        self.prjSetupLayout.addWidget(self.prjNameLabel)
        self.prjSetupLayout.addWidget(self.prjNameEdit)
        self.prjSetupLayout.addWidget(self.prjSelect)

        # UPLOAD
        self.uploadLabel = QLabel('upload', widget)
        self.uploadFull = QCheckBox('upload full quality media', widget)
        self.uploadFull.stateChanged.connect(self.onUploadFullChecked)

        self.uploadLabel.setFont(self.sectionFont)
        self.upload_layout = QVBoxLayout(widget)
        self.upload_layout.addWidget(self.uploadLabel)
        self.upload_layout.addWidget(self.uploadFull)

        self.bot_row_layout = QHBoxLayout(widget)
        self.bot_row_layout.addLayout(self.upload_layout)

        # SETUP TRNLA LAYOUT
        self.trnla_layout.addLayout(self.projectModesHBox)
        self.trnla_layout.addLayout(self.prjSetupLayout)
        self.trnla_layout.addLayout(self.bot_row_layout)
        self.trnla_layout.addLayout(self.logout)
        self.newProject.setCheckState(Qt.Checked)
        # --------------------------------------------

        if self.api_key:
            # logged in ui
            QTimer.singleShot(0, lambda: self.loggedInMode(onStart=True))
        else:
            # logged out ui
            QTimer.singleShot(0, self.loggedOutMode)

        main_layout.addLayout(self.trnla_layout)

    def loggedOutMode(self):
        self.preset().properties()["trnla_upload"] = False
        self.preset().properties()["trnla_api_key"] = ""
        self.loginBtn.show()
        self.message.show()

        self.newProject.hide()
        self.existProject.hide()
        self.prjSelect.hide()
        self.prjSelect.clear()
        self.prjNameEdit.setText('')
        self.prjNameEdit.hide()
        self.logoutBtn.hide()
        self.prjNameLabel.hide()
        self.prjSelect.hide()
        self.uploadLabel.hide()
        self.uploadFull.hide()

    def requestProjects(self):
        self.location = 'https://trn.la/api/producer/projects'
        self.url = QUrl(self.location)
        self.data = QByteArray()
        self.request = QNetworkRequest(self.url)
        self.data.append("api_key=" + str(self.api_key))
        self.request.setHeader(QNetworkRequest.ContentTypeHeader,
                               'application/x-www-form-urlencoded')
        if self.api_key:
            self.nam.post(self.request, self.data)

    def loggedInMode(self, onStart):
        self.uploadFull.setCheckState(Qt.Checked)
        self.newProject.setCheckState(Qt.Checked)
        self.preset().properties()["trnla_upload"] = True
        self.api_key = self.get_api_key()
        self.preset().properties()["trnla_api_key"] = self.api_key
        if not onStart:
            self.requestProjects()

        self.loginBtn.hide()
        self.message.hide()

        self.newProject.show()
        self.existProject.show()
        self.prjSelect.hide()
        self.prjNameEdit.show()
        self.logoutBtn.show()
        self.prjNameLabel.show()
        self.prjSelect.hide()
        self.uploadLabel.show()
        self.uploadFull.show()

    def onLogOut(self):
        TarantulaData = os.path.expanduser("~") + '/AppData/Local/Tarantula/'
        configJsonFile = TarantulaData + 'config.json'
        try:
            jsonFile = open(configJsonFile)
        except Exception as err:
            jsonFile = None

        if jsonFile:
            jsonFile.close()
            os.remove(configJsonFile)

        self.loggedOutMode()
        pass


class TrnlaShotProcessor(FnShotProcessor.ShotProcessor):
    def __init__(self, preset, submission=None, synchronous=False):
        FnShotProcessor.ShotProcessor.__init__(self, preset, submission, synchronous)

    def findAndDeletePreview(self, ele):
        if ele is None:
            return 'None'

        am_prev_dir = ''
        children = ele.children()
        for child in children[:-1]:
            result = self.findAndDeletePreview(child)
            if result == 'Prev':
                ele.removeChild(child)
                am_prev_dir = 'am_prev_dir'
            elif result == 'am_prev_dir':
                ele.removeChild(child)

        if ele.childCount():
            result = self.findAndDeletePreview(children[-1])
            if result == 'Prev':
                ele.removeChild(children[-1])
                am_prev_dir = 'am_prev_dir'
            elif result == 'am_prev_dir':
                ele.removeChild(children[-1])

        if type(ele.preset()) == TrnlaPreviewTranscoderPreset:
            return 'Prev'
        elif am_prev_dir == 'am_prev_dir':
            return am_prev_dir
        else:
            return 'Not_Prev'

    def readyRead(self, reply):
        er = reply.error()

        if er == QNetworkReply.NoError:
            bytes_string = reply.readAll()
            data = str(bytes_string).decode('utf8')
            replyJson = json.loads(data)
            if replyJson.get('success'):
                newProjId = replyJson.get('project_id')
                if newProjId:
                    self.preset().properties()["trnla_project_id"] = newProjId
                    self.TrnlaStartProcessing(self.trnlaExportItems, self.trnlaPreview)
        else:
            print("Error occurred: ", er)
            print(reply.errorString())

    def reply_error_occurred(self, err):
        print("reply error (" + self._shot_name + ") :" + str(err))

    def create_project(self):
        # Get Sequence Info
        project_info = self.getSeqInfo(self.trnlaExportItems) + (self.getColorSpace(),)

        self.location = 'https://trn.la/api/producer/store_project'
        self.url = QUrl(self.location)
        self.data = QByteArray()
        self.nam = QNetworkAccessManager()
        self.request = QNetworkRequest(self.url)

        self.multpart = QHttpMultiPart(QHttpMultiPart.FormDataType)
        api_part = QHttpPart()
        api_part.setHeader(QNetworkRequest.ContentDispositionHeader, "form-data; name=\"api_key\"")
        api_part.setBody(self.preset().properties()["trnla_api_key"].encode())
        self.multpart.append(api_part)

        name_part = QHttpPart()
        name_part.setHeader(QNetworkRequest.ContentDispositionHeader, "form-data; name=\"name\"")
        name_part.setBody(self.preset().properties()["trnla_project_name"].encode())
        self.multpart.append(name_part)

        fps_part = QHttpPart()
        fps_part.setHeader(QNetworkRequest.ContentDispositionHeader, "form-data; name=\"frame_rate\"")
        fps_part.setBody(project_info[0].encode())
        self.multpart.append(fps_part)

        width_part = QHttpPart()
        width_part.setHeader(QNetworkRequest.ContentDispositionHeader, "form-data; name=\"width\"")
        width_part.setBody(project_info[1].encode())
        self.multpart.append(width_part)

        height_part = QHttpPart()
        height_part.setHeader(QNetworkRequest.ContentDispositionHeader, "form-data; name=\"height\"")
        height_part.setBody(project_info[2].encode())
        self.multpart.append(height_part)

        color_part = QHttpPart()
        color_part.setHeader(QNetworkRequest.ContentDispositionHeader, "form-data; name=\"color_space\"")
        color_part.setBody(project_info[3].encode())
        self.multpart.append(color_part)


        self.request.setHeader(QNetworkRequest.ContentTypeHeader,
                                      'multipart/form-data; boundary=%s' % self.multpart.boundary())

        self.customEventLoop = QEventLoop()
        self.nam.finished.connect(self.readyRead)
        self.nam.finished.connect(self.customEventLoop.quit)

        self.reply = self.nam.post(self.request, self.multpart)
        self.reply.error.connect(self.reply_error_occurred)

        self.customEventLoop.exec_()

    def TrnlaStartProcessing(self, exportItems, preview):
        for (exportPath, preset) in self._exportTemplate.flatten():
            if "trnla_upload" in preset.properties():
                preset.properties()["trnla_upload"] = self.preset().properties()["trnla_upload"]
                if "trnla_project_id" in preset.properties():
                    preset.properties()["trnla_project_id"] = self.preset().properties()["trnla_project_id"]
                    preset.properties()["trnla_new_project"] = self.preset().properties()["trnla_new_project"]
                    preset.properties()["trnla_exist_project"] = self.preset().properties()["trnla_exist_project"]
                    preset.properties()["trnla_project_name"] = self.preset().properties()["trnla_project_name"]
                    preset.properties()["trnla_api_key"] = self.preset().properties()["trnla_api_key"]

        exporters = FnShotProcessor.ShotProcessor.startProcessing(self, exportItems, preview)
        if self.preset().properties()["trnla_upload"]:
            full_transcoders = []
            prev_transcoders = []
            for exporter in exporters:
                if type(exporter) is TrnlaTranscodeExporter:
                    full_transcoders.append(exporter)
                elif type(exporter) is TrnlaPreviewTranscoder:
                    prev_transcoders.append(exporter)
            for full in full_transcoders:
                item_id = full._item.guid()
                for prev in prev_transcoders:
                    if item_id == prev._item.guid():
                        prev.notifier.preview_ready[str].connect(full.upload_shot)

    def getSeqInfo(self, exportItems):
        """This code is mainly from FnExternalRender"""
        sequences = []
        # Track items were selected
        if exportItems[0].trackItem():
            sequences.append(exportItems[0].trackItem().parent().parent())
        else:
            # Items were selected in the project panel. Build a list of selected sequences
            sequences = [item.sequence() for item in exportItems if item.sequence() is not None]

        for seq in sequences:
            return str(seq.framerate()), str(seq.format().width()), str(seq.format().height())

    def getColorSpace(self):
        preset = None
        for (exportPath, _preset) in self._exportTemplate.flatten():
            if "trnla_project_id" in _preset.properties():
                preset = _preset
                break

        if preset:
            """This code is mainly from FnExternalRender.createWriteNode()"""
            try:
                properties = preset.properties()
                project = hiero.core.projects()[-1]
                colourTransform = properties.get("colourspace", None)
                if colourTransform:
                    # If a non-default colour transform is set, validate that it actually exists
                    # in the current project configuration.  This check should probably be done
                    # earlier, but there's no appropriate place to do it.
                    isTransformDefault = colourTransform == "default"
                    isValidTransform = isTransformDefault or getRoleFromProperty(colourTransform) in hiero.core.LUTs(project)
                    if not isValidTransform:
                        raise RuntimeError("Unable to create Write node with invalid color space: %s" % colourTransform)

                    colourSpace = getColorspaceFromProperty(properties["colourspace"])
                    projectsettings = project.extractSettings()
                    colourTransform = FnNukeHelpers.nukeColourTransformNameFromHiero(colourSpace, projectsettings)

                projectsettings = project.extractSettings()
                if projectsettings["lutUseOCIOForExport"] is True:
                    # If the colour transform hasnt been set or if set to default,
                    # we need to mimic the default colourspace of nukes write node
                    # Using the colour
                    if colourTransform in (None, "default"):
                            colourTransform = _mapDefaultColourTransform(preset, projectsettings)
                if colourTransform is not None:
                    # Little hack to get the name of the colourspace in case default was selected.
                    w = nuke.createNode('Write')
                    colorSpaces = w.knob('colorspace').values()
                    nuke.delete(w)
                    tabColourTransform = '\t' + colourTransform
                    for cs in colorSpaces:
                        if tabColourTransform in cs:
                            _cs = cs.split('\t', 1)[1]
                            colourTransform = getColorspaceFromProperty(_cs)
                            break
                    return colourTransform
            except Exception as e:
                return "None"
        return "None"

    def startProcessing(self, exportItems, preview=False):
        if preview:
            return FnShotProcessor.ShotProcessor.startProcessing(self, exportItems, preview)

        if not self.preset().properties()["trnla_upload"]:
            self.findAndDeletePreview(self._exportTemplate.rootElement())
            self.TrnlaStartProcessing(exportItems, preview)
        else:
            if self.preset().properties()["trnla_new_project"]:
                self.trnlaExportItems = exportItems
                self.trnlaPreview = preview
                self.create_project()
            elif self.preset().properties()["trnla_exist_project"]:
                self.TrnlaStartProcessing(exportItems, preview)


class TrnlaShotProcessorPreset(hiero.core.ProcessorPreset):
    def __init__(self, name, properties):
        hiero.core.ProcessorPreset.__init__(self, TrnlaShotProcessor, name)

        # setup defaults
        self._excludedTrackIDs = []
        self.nonPersistentProperties()["excludedTracks"] = []
        self.properties()["excludeTags"] = []
        self.properties()["includeTags"] = []
        self.properties()["versionIndex"] = 1
        self.properties()["versionPadding"] = 2
        self.properties()["exportTemplate"] = ( )
        self.properties()["exportRoot"] = "{projectroot}"
        self.properties()["cutHandles"] = 12
        self.properties()["cutUseHandles"] = False
        self.properties()["cutLength"] = False
        self.properties()["includeRetimes"] = False
        self.properties()["startFrameIndex"] = 1001
        self.properties()["startFrameSource"] = TrnlaShotProcessor.kStartFrameSource

        self.properties()["trnla_project_id"] = ""
        self.properties()["trnla_new_project"] = True
        self.properties()["trnla_exist_project"] = False
        self.properties()["trnla_project_name"] = ""
        self.properties()["trnla_upload"] = False
        self.properties()["trnla_project_names"] = []
        self.properties()["trnla_project_ids"] = []
        self.properties()["trnla_api_key"] = ""

        self.properties().update(properties)

        # This remaps the project root if os path remapping has been set up in the preferences
        self.properties()["exportRoot"] = hiero.core.remapPath(self.properties()["exportRoot"])

    def get_org_dir(self):
        TarantulaData = os.path.expanduser("~") + '/AppData/Local/Tarantula/'
        configJsonFile = TarantulaData + 'config.json'
        try:
            with open(configJsonFile) as jsonFile:
                config = json.load(jsonFile)
                settings = config['settings']
                job_dir = settings['organization_directory']

                return job_dir.encode("ascii")
        except Exception as err:
            return ""

    def addCustomResolveEntries(self, resolver):
        """addDefaultResolveEntries(self, resolver)
        Create resolve entries for default resolve tokens shared by all task types.
        @param resolver : ResolveTable object"""

        resolver.addResolver("{filename}", "Filename of the media being processed", lambda keyword, task: task.fileName())
        resolver.addResolver(kFileBaseKeyword, KeywordTooltips[kFileBaseKeyword], lambda keyword, task: task.filebase())
        resolver.addResolver(kFileHeadKeyword, KeywordTooltips[kFileHeadKeyword], lambda keyword, task: task.filehead())
        resolver.addResolver(kFilePathKeyword, KeywordTooltips[kFilePathKeyword], lambda keyword, task: task.filepath())
        resolver.addResolver("{filepadding}", "Source Filename padding for formatting frame indices", lambda keyword, task: task.filepadding())
        resolver.addResolver("{fileext}", "Filename extension part of the media being processed", lambda keyword, task: task.fileext())
        resolver.addResolver("{clip}", "Name of the clip used in the shot being processed", lambda keyword, task: task.clipName())
        resolver.addResolver("{shot}", "Name of the shot being processed", lambda keyword, task: task.shotName())
        resolver.addResolver("{track}", "Name of the track being processed", lambda keyword, task: task.trackName())
        resolver.addResolver("{sequence}", "Name of the sequence being processed", lambda keyword, task: task.sequenceName())
        resolver.addResolver("{event}", "EDL event of the track item being processed", lambda keyword, task: task.editId())
        resolver.addResolver("{_nameindex}", "Index of the shot name in the sequence preceded by an _, for avoiding clashes with shots of the same name", lambda keyword, task: task.shotNameIndex())
        resolver.addResolver("{trnla_jobs}", "Tarantula organization job directory", lambda keyword, task: self.get_org_dir())
        resolver.addResolver("{trnla_project_name}", "Tarantula project to add the shot to.", self.properties()["trnla_project_name"])

    # check that all nuke shot exporters have at least one write node
    def isValid(self):
        allNukeShotsHaveWriteNodes = True
        for itemPath, itemPreset in self.properties()["exportTemplate"]:
            isNukeShot = isinstance(itemPreset, hiero.exporters.FnNukeShotExporter.NukeShotPreset)
            if isNukeShot and not itemPreset.properties()["writePaths"]:
                allNukeShotsHaveWriteNodes = False
                return (False, "Your Export Structure has no Write Nodes defined.")
        return (True, "")
