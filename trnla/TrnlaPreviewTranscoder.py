# --------------------------Trn.la Plugin For Nuke Studio--------------------------------
# Subclass of TranscodeExporter that handles exporting mp4 previews for upload.
#
# (c) 2021 Tarantula
# Author: Moses Molina
# email:  moses.tarantula@gmail.com
# --------------------------------------------------------------------------------------

import os
import json
import zipfile

import hiero.core

from hiero.exporters import FnTranscodeExporter, FnTranscodeExporterUI, FnExternalRenderUI, FnExternalRender, \
    FnAudioHelper

from PySide2.QtNetwork import *
from PySide2.QtCore import *
from PySide2.QtWidgets import *


class TrnlaUploaderNotifier(QObject):
    preview_ready = Signal(str)

    def __init__(self):
        QObject.__init__(self)

    def notify_uploader(self, path):
        self.preview_ready.emit(path)


class TrnlaPreviewTranscoder(FnTranscodeExporter.TranscodeExporter):
    def __init__(self, initDict):
        FnTranscodeExporter.TranscodeExporter.__init__(self, initDict)
        self.notifier = TrnlaUploaderNotifier()

    def startTask(self):
        FnTranscodeExporter.TranscodeExporter.startTask(self)

    def progress(self):
        return float(FnTranscodeExporter.TranscodeExporter.progress(self))

    def finishTask(self):
        path = self.resolvedExportPath()
        FnTranscodeExporter.TranscodeExporter.finishTask(self)
        self.notifier.notify_uploader(path)


class TrnlaPreviewTranscoderPreset(FnTranscodeExporter.TranscodePreset):
    def __init__(self, name, properties):
        hiero.core.RenderTaskPreset.__init__(self, TrnlaPreviewTranscoder, name, properties)

        # Set any preset defaults here
        self.properties()["keepNukeScript"] = False
        self.properties()["readAllLinesForExport"] = self._defaultReadAllLinesForCodec()
        self.properties()["useSingleSocket"] = False
        self.properties()["burninDataEnabled"] = False
        self.properties()["burninData"] = dict(
            (datadict["knobName"], None) for datadict in FnExternalRender.NukeRenderTask.burninPropertyData)
        self.properties()["additionalNodesEnabled"] = False
        self.properties()["additionalNodesData"] = []
        self.properties()["method"] = "Blend"
        self.properties()["includeEffects"] = True
        self.properties()["includeAudio"] = False
        self.properties()["deleteAudio"] = True

        self.properties()["trnla_upload"] = False

        FnAudioHelper.defineExportPresetProperties(self)

        # Give the Write node a name, so it can be referenced elsewhere
        if "writeNodeName" not in self.properties():
            self.properties()["writeNodeName"] = "Write_{ext}"

        self.properties().update(properties)

    def supportedItems(self):
        return hiero.core.TaskPresetBase.kAllItems


class TrnlaPreviewTranscoderUI(FnTranscodeExporterUI.TranscodeExporterUI):
    def __init__(self, preset):
        FnExternalRenderUI.NukeRenderTaskUI.__init__(self, preset, TrnlaPreviewTranscoder, "Trnla Transcode Preview")
        self._tags = []

    def populateUI(self, widget, exportTemplate):
        FnTranscodeExporterUI.TranscodeExporterUI.populateUI(self, widget, exportTemplate)

    def createFileTypeWidget(self, layout):
        codecComboToolTip = "The output image type for rendered images."
        index = 0
        presetFileType = self._preset._properties["file_type"]
        self._codecTypeComboBox = QComboBox()
        self._codecTypeComboBox.setToolTip(codecComboToolTip)

        if presetFileType not in self._codecSettings:
            presetFileType = self._codecSettings.keys()[0]

        for file_type in sorted(self._codecSettings.keys()):
            self._codecTypeComboBox.addItem(file_type)
            if str(file_type) == str(presetFileType):
                self._codecTypeComboBox.setCurrentIndex(index)
            index += 1

        self._codecTypeComboBox.currentIndexChanged.connect(self.codecTypeComboBoxChanged)
        # Trnla needs the preview file to be of a specific type so we want to make sure the user only has certain
        # options here. For now It will default to mov/h.264.
        # layout.addRow("File Type:", self._codecTypeComboBox)
