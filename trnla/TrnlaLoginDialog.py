# --------------------------Trn.la Plugin For Nuke Studio--------------------------------
# QDialog for logging into a trnla account.
# 
# (c) 2021 Tarantula
# Author: Moses Molina
# ---------------------------------------------------------------------------------------

from PySide2.QtGui import *
from PySide2.QtCore import *
from PySide2.QtWidgets import *
from PySide2.QtNetwork import *

import os
import os.path as path
import json
import nuke

class TrnlaLoginDialog(QDialog):
    def __init__(self, parent=None):
        QDialog.__init__(self, parent)
        self.setWindowTitle("trnl.la login")
        self.setMinimumSize(450, 350)

        # Layouts
        layout = self.layout = QVBoxLayout()

        # LOGO
        logo_png = path.abspath(path.dirname(path.relpath(__file__)).replace('\\', '/') + "/tarantula.png").replace('\\', '/')
        if logo_png:
            logo = QPixmap(logo_png)
        else:
            logo = QPixmap()
        self.logoLabel = QLabel()
        self.logoLabel.setPixmap(logo.scaled(200, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.logo = QHBoxLayout()
        self.logo.addStretch()
        self.logo.addWidget(self.logoLabel)
        self.logo.addStretch()

        # Create Widgets
        self.username = QLineEdit()
        self.username.setPlaceholderText('email')
        self.password = QLineEdit()
        self.password.setPlaceholderText('password')
        self.password.setEchoMode(QLineEdit.Password)

        self.status = QHBoxLayout()
        self.statusL = QLabel()
        self.status.addWidget(self.statusL)
        self.status.addStretch()

        self.loginBtn = QPushButton('Sign In')
        # self.loginBtn.setFlat(True)
        self.loginBtn.setObjectName('sign_in_btn')
        self.loginBtn.setMinimumSize(100, 30)
        self.loginBtn.setStyleSheet('#sign_in_btn {	background-color: #008CDE;    border: 5px;    border-radius: 3px;	border-color: rgb(20,20,20);	color: rgb(220, 220, 220);} #sign_in_btn:hover{	background-color: rgb(30, 130, 255);} #sign_in_btn:pressed{	background-color: rgb(14, 100, 240);}')
        self.loginBtn.clicked.connect(self.Login)
        self.btnBox = QHBoxLayout()
        self.btnBox.addStretch()
        self.btnBox.addWidget(self.loginBtn)
        self.btnBox.addStretch()

        self.jobsH = QHBoxLayout()
        self.jobsH.setSpacing(2)
        self.jobsE = QLineEdit()
        self.jobsE.setPlaceholderText('Choose a job directory')
        self.jobsBtn = QPushButton('Choose ...')
        self.jobsBtn.setObjectName('create_browse')
        self.jobsBtn.clicked.connect(self.onChoose)
        self.jobsH.addWidget(self.jobsE)
        self.jobsH.addWidget(self.jobsBtn)

        # Setup Layouts
        layout.addStretch(1)
        layout.addLayout(self.logo)
        layout.addStretch(1)
        layout.addLayout(self.jobsH)
        layout.addWidget(self.username)
        layout.addWidget(self.password)
        layout.addLayout(self.status)
        layout.addStretch(3)
        layout.addLayout(self.btnBox)
        layout.addStretch(1)

        self.setLayout(layout)

    def onChoose(self):
        chosenPath = nuke.getFilename('Choose a job directory - Where shots will export to unless specified otherwise.')
        self.jobsE.setText(chosenPath)

    def Login(self):
        if os.path.isdir(self.jobsE.text()):
            self.loginBtn.setEnabled(False)
            self.username.deselect()
            self.password.deselect()
            self.nam = QNetworkAccessManager()
            self.nam.finished[QNetworkReply].connect(self.nam_finished)

            data = QByteArray()
            email = str("email=" + self.username.text() + "&")
            data.append(email)
            pwd = str("password=" + self.password.text())
            data.append(pwd)

            url = QUrl()
            url.setUrl('https://trn.la/api/producer/login')
            self.request = QNetworkRequest(url)
            self.reply = self.nam.post(self.request, data)
            self.reply.error.connect(self.reply_error_occurred)
        else:
            self.statusL.setText("<b><font color=\"#cc0000\">Chosen folder is not a real directory!</font></b>")

    def reply_error_occurred(self, err):
        print("reply error:" + str(err))

    def success(self):
        QTimer.singleShot(1000, self.accept)

    def nam_finished(self, reply):
        er = reply.error()

        if er == QNetworkReply.NoError:
            bytes_string = reply.readAll()
            data = json.loads(str(bytes_string).encode('utf-8'))

            if data['class'] == 'success':
                self.statusL.setText("<b><font color=\"#00cc44\">success!</font></b>")
                userdata = data['data']
                org_info = data['organization']

                jobs_dir = self.jobsE.text()
                if jobs_dir.endswith('/') or jobs_dir.endswith('\\'):
                    jobs_dir = jobs_dir[:-1]
                if jobs_dir.endswith('/') or jobs_dir.endswith('\\'):
                    jobs_dir = jobs_dir[:-1]
                if os.path.basename(jobs_dir) != org_info["name"]:
                    jobs_dir += '/' + org_info["name"]
                jobs_dir.replace('\\', '/')

                settings = {
                    "organization_name": org_info["name"],
                    "projects_directory": "",
                    "organization_directory": jobs_dir,
                    "common_directory": "",
                    "has_profile_picture": "",
                    "username": self.username.text(),
                    "api_key": data['token'],
                    "data": userdata,
                    "rendering_enabled": False
                }
                doc = {'settings': settings}

                TarantulaData = os.path.expanduser("~") + '/AppData/Local/Tarantula/'
                configJsonFile = TarantulaData + 'config.json'
                try:
                    if not os.path.exists(os.path.dirname(configJsonFile)):
                        os.makedirs(os.path.dirname(configJsonFile))

                    if not os.path.exists(jobs_dir):
                        os.makedirs(jobs_dir)

                    with open(configJsonFile, 'w') as outfile:
                        json.dump(doc, outfile, indent=4, sort_keys=True)
                        outfile.close()
                        QTimer.singleShot(0, self.success)
                except Exception as e:
                    self.statusL.setText("<b><font color=\"#ff3030\">Error during org setup:" + str(e) + "</font></b>")
            else:
                self.statusL.setText("<b><font color=\"#ff3030\">username or password is incorrect</font></b>")
        else:
            self.statusL.setText("<b><font color=\"#ff3030\">Error trying to log in</font></b>")

        self.loginBtn.setEnabled(True)

