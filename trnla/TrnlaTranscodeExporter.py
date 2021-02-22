# --------------------------Trn.la Plugin For Nuke Studio--------------------------------
# Subclass of TranscodeExporter that handles exporting full quality media and uploading
# the shot to trn.la.
#
# Author: Moses Molina
# email:  moses.tarantula@gmail.com
# --------------------------------------------------------------------------------------

import os
import json
import zipfile
import re
import copy

import hiero.core
import hiero.core.log as log

from hiero.exporters import FnTranscodeExporter, FnTranscodeExporterUI, FnExternalRenderUI, FnExternalRender, FnAudioHelper

from hiero.exporters.FnSubmission import Submission

from PySide2.QtNetwork import *
from PySide2.QtCore import *
from PySide2.QtWidgets import *


class TrnlaTranscodeExporter(FnTranscodeExporter.TranscodeExporter):
    def __init__(self, initDict):
        FnTranscodeExporter.TranscodeExporter.__init__(self, initDict)
        self.uploaded = False
        self.upload_started = False
        self.fullFilePath = ""
        self.fileDir = ""
        self.fullFileName = ""
        self.root = ""
        self.ext = ""
        self.upload_progress = 0.0
        self.upload_reply = None
        self._shot_name = None

    def startTask(self):
        if self._preset.properties()["trnla_api_key"] == "none" and self._preset.properties()["trnla_upload"]:
            msg = "Please log in to trn.la before using the trying to upload."
            self.setError(msg)
            self._progress = 1.0
            self._finished = True
            return
        else:
            self._shot_name = self.shotName()
            self.fullFilePath = self.resolvedExportPath()
            self.fileDir, self.fullFileName = os.path.split(self.fullFilePath)
            FnTranscodeExporter.TranscodeExporter.startTask(self)

    def progress(self):
        if self._preset.properties()["trnla_upload"]:
            if self.uploaded:
                return 1.0
            else:
                _p = FnTranscodeExporter.TranscodeExporter.progress(self)
                if _p > 1.0:
                    _p = 1.0
                return (_p / 2.0) + (self.upload_progress / 2.05)
        else:
            return float(FnTranscodeExporter.TranscodeExporter.progress(self))

    def zipdir(self, path, ziph):
        # ziph is zipfile handle
        for root, dirs, files in os.walk(path):
            for file in files:
                file_root, ext = os.path.splitext(file)
                if ext == self.ext:
                    file_to_write = os.path.join(root, file)
                    ziph.write(file_to_write, os.path.basename(file_to_write))

    def upload_finished(self, reply):
        self.uploaded = True
        self._finished = True
        self.prev_file.close()
        self.zip_file.close()

    def onUploadProgress(self, bytes_sent, bytes_total):
        if bytes_total:
            self.upload_progress = float(bytes_sent) / bytes_total

    def reply_error_occurred(self, err):
        print("reply error (" + self._shot_name + ") :" + str(err))

    def upload_shot(self, prev_file_path):
        self.net_man = QNetworkAccessManager()
        self.net_man.finished[QNetworkReply].connect(self.upload_finished)
        self.upload_started = True
        # zip the files
        self.root, self.ext = os.path.splitext(self.fullFileName)

        zipPath = os.path.join(os.path.dirname(self.fileDir), os.path.basename(os.path.normpath(self.fileDir)) + '.zip')
        zipPath = zipPath.replace('\\', '/')
        zipf = zipfile.ZipFile(zipPath, 'w', zipfile.ZIP_DEFLATED)
        self.zipdir(self.fileDir + '/', zipf)
        zipf.close()

        # upload
        self.multpart = QHttpMultiPart(QHttpMultiPart.FormDataType)
        api_part = QHttpPart()
        api_part.setHeader(QNetworkRequest.ContentDispositionHeader, "form-data; name=\"api_key\"")
        api_part.setBody(self._preset.properties()["trnla_api_key"].encode())
        self.multpart.append(api_part)

        proj_id_part = QHttpPart()
        proj_id_part.setHeader(QNetworkRequest.ContentDispositionHeader, "form-data; name=\"project_id\"")
        proj_id_part.setBody(str(self._preset.properties()["trnla_project_id"]).encode())
        self.multpart.append(proj_id_part)

        shot_name_part = QHttpPart()
        shot_name_part.setHeader(QNetworkRequest.ContentDispositionHeader, "form-data; name=\"shot_name\"")
        shot_name_part.setBody(self._shot_name)
        self.multpart.append(shot_name_part)

        self.zip_file = QFile(zipPath)
        if not self.zip_file.open(QIODevice.ReadOnly):
            print('failed to open zip')
            return
        shot_file_part = QHttpPart()
        shot_file_part.setHeader(QNetworkRequest.ContentDispositionHeader,
                                 "form-data; name=\"shot_file\"; filename=\"" + zipPath + "\"")
        shot_file_part.setBodyDevice(self.zip_file)
        self.multpart.append(shot_file_part)

        self.prev_file = QFile(prev_file_path)
        if not self.prev_file.open(QIODevice.ReadOnly):
            print('failed to open mp4 preview')
            return
        prev_file_part = QHttpPart()
        prev_file_part.setHeader(QNetworkRequest.ContentDispositionHeader,
                                 "form-data; name=\"preview_file\"; filename=\"" + os.path.basename(prev_file_path) + "\"")
        prev_file_part.setBodyDevice(self.prev_file)
        self.multpart.append(prev_file_part)

        url = "https://dev.trn.la/api/producer/store"
        self.upload_request = QNetworkRequest(url)
        self.upload_request.setHeader(QNetworkRequest.ContentTypeHeader,
                                      'multipart/form-data; boundary=%s' % self.multpart.boundary())

        self.upload_reply = self.net_man.post(self.upload_request, self.multpart)
        self.upload_reply.uploadProgress.connect(self.onUploadProgress)
        self.upload_reply.error.connect(self.reply_error_occurred)

    def stop_upload(self):
        if self.upload_reply:
            self.upload_reply.abort()

    def finishTask(self):
        if self._preset.properties()["trnla_api_key"] != "none" and self._preset.properties()["trnla_upload"]:
            if not self.uploaded and not self.upload_started:
                self._finished = False
            else:
                if not self.uploaded:
                    self.stop_upload()
                FnTranscodeExporter.TranscodeExporter.finishTask(self)
        else:
            self.stop_upload()
            FnTranscodeExporter.TranscodeExporter.finishTask(self)



class TrnlaTranscodePreset(FnTranscodeExporter.TranscodePreset):
    def __init__(self, name, properties):
        hiero.core.RenderTaskPreset.__init__(self, TrnlaTranscodeExporter, name, properties)

        # Set any preset defaults here
        self.properties()["keepNukeScript"] = False
        self.properties()["readAllLinesForExport"] = self._defaultReadAllLinesForCodec()
        self.properties()["useSingleSocket"] = False
        self.properties()["burninDataEnabled"] = False
        self.properties()["burninData"] = dict((datadict["knobName"], None) for datadict in FnExternalRender.NukeRenderTask.burninPropertyData)
        self.properties()["additionalNodesEnabled"] = False
        self.properties()["additionalNodesData"] = []
        self.properties()["method"] = "Blend"
        self.properties()["includeEffects"] = True
        self.properties()["includeAudio"] = False
        self.properties()["deleteAudio"] = True

        self.properties()["trnla_upload"] = False
        self.properties()["trnla_project_id"] = ""
        self.properties()["trnla_new_project"] = True
        self.properties()["trnla_exist_project"] = False
        self.properties()["trnla_project_name"] = ""
        self.properties()["trnla_api_key"] = "none"

        FnAudioHelper.defineExportPresetProperties(self)

        # Give the Write node a name, so it can be referenced elsewhere
        if "writeNodeName" not in self.properties():
          self.properties()["writeNodeName"] = "Write_{ext}"

        self.properties().update(properties)

    def supportedItems(self):
        return hiero.core.TaskPresetBase.kAllItems


class TrnlaTranscodeExporterUI(FnTranscodeExporterUI.TranscodeExporterUI):
    def __init__(self, preset):
        FnExternalRenderUI.NukeRenderTaskUI.__init__(self, preset, TrnlaTranscodeExporter, "Trnla Transcode Images")
        self._tags = []