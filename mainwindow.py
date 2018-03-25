# -*- coding: utf-8 -*-
import platform
import os
import datetime
import subprocess
import sys
import dateutil.parser
import pprint as pp
import codecs

sysisDarwin = platform.system() == 'Darwin'
sysisWindows = platform.system() == 'Windows'

if sysisDarwin:
    #from  import NSURL
    from Foundation import NSURL
# else:
#     from knownpaths import *

from mainwindow_ui import *
from deadlinecalc import DeadLineCalc
from StatusLabel import StatusLabel

from PySide import QtGui
from PySide import QtCore

from PySide.QtCore import QSettings
from PySide.QtCore import QObject
from PySide.QtCore import QDateTime

from PySide.QtGui import QDesktopServices
from pprint import pprint

# for debug
# from pprint import pprint

class MainWindow(QtGui.QMainWindow,Ui_MainWindow):

    '''
    deadlinecalc メインウインドウ
    '''

    __version__ = "1.1.2"

    CORP_INFO = 'LespaceVision'

    OPT_PRJLASTHIST = 'lastprj' # 最後に使用した案件名文字列
    OPT_PRJHIST = 'histprj'     # 直近10個くらいまでの案件名文字列
    OPT_LOGMODE   = 'logmode'   # True=Log取得する,False=Log取得しない
    OPT_DEBUGMODE = 'debugmode' # True=デバッグログ取得する,False=デバッグログ取得しない

    Logdir = "Log"
    DebugDir = "Debug"

    msgBox = ""

    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent)

        self.setupUi(self)
        self.mainToolBar.hide()

        #self.rpack = RapidPack(self)
        self.appname = 'DeadlineCalc'
        self.calc = DeadLineCalc(self)

        self.msgBox = QtGui.QMessageBox()
        self.msgBox.setWindowTitle(self.appname)
        self.msgBox.setIcon(QtGui.QMessageBox.Critical)

        self.checkedcount = 0 #ジョブリスト中のチェックされてるジョブの数

        if not self.calc.connectServer():
            # QMessageBoxかなんか出してやるかあ
            # print("Can't Connect Deadline Server.")
            errstr = "Can't Connect Deadline Server."
            self.msgBox.setText(errstr)
            self.msgBox.setInformativeText(self.calc.errmessage)
            self.msgBox.setStandardButtons(QtGui.QMessageBox.Ok)
            self.msgBox.exec_()

            sys.exit(-1)

        # 先にユーザ一覧取得しちゃおうかなー。
        #
        if not self.calc.getUserandProject():
            # print("getUserandProject()")
            errstr = "Error: getUserandProject() Failed."
            self.msgBox.setText(errstr)
            self.msgBox.setInformativeText(self.calc.errmessage)
            self.msgBox.setStandardButtons(QtGui.QMessageBox.Ok)
            self.msgBox.exec_()
            sys.exit(-1)

        #self.aboutdialog.__init__("aaa")

        QSettings.setDefaultFormat(QSettings.NativeFormat)
        QtCore.QCoreApplication.setOrganizationName(self.CORP_INFO)

        self.timerid = 0
        self.dot_count = 0
        self.status_label = StatusLabel("")

        self.early_subdate = 0   # calc期間のもっとも早い送信日時
        self.late_enddate = 0    # calc期間のもっとも遅い終了日時

        #面倒だから内部ver表記でいいやあ
        verstr = "{0} v{1}".format(self.appname,self.__version__)
        self.setWindowTitle(verstr)

        QtCore.QCoreApplication.setApplicationName(self.appname)

        # Log保存用フォルダ作成
        # if (sysisWindows):
        #
        #     try:
        #         self.dochome = os.path.join(get_path(FOLDERID.Documents, user_handle=None), self.appname)
        #
        #     except PathNotFoundException as patherr:
        #
        #
        #         os.sys.exit(-1)
        #         # print(self.dochome)
        # else:
        #     self.dochome = os.path.join(os.path.expanduser('~/Documents'), self.appname)
        # if not os.path.exists(self.dochome):
        #     os.mkdir(self.dochome)
        #
        # if not os.path.exists(os.path.join(self.dochome,self.Logdir)):
        #     os.mkdir(os.path.join(self.dochome,self.Logdir))
        #
        # #self.rpack.setdochome(self.dochome)
        #
        # #self.cfg = QSettings()
        # self.cfg = QSettings(self.dochome + "/" + self.appname + ".ini",QSettings.IniFormat)


        #self.plainTextEdit_jobID

        self.__initEv()
        self.__readsettings()

    def __initEv(self):

        self.statusBar.setLayoutDirection(QtCore.Qt.RightToLeft)
        self.statusBar.setSizeGripEnabled(False)
        self.statusBar.addPermanentWidget(self.status_label)

        # comboboxのプルダウンリストのmaxを増やすよん
        self.comboBox_UserName.setMaxVisibleItems(50)
        self.comboBox_ProjectName.setMaxVisibleItems(50)

        self.pushButton_Search.clicked.connect(self.search_clicked)
        self.pushButton_Calc.clicked.connect(self.calc_clicked)
        self.pushButton_Reloaduser.clicked.connect(self.reload_clicked)
        self.pushButton_calcclear.clicked.connect(self.calcclear_clicked)
        self.pushButton_csvout.clicked.connect(self.csvout_clicked)
        self.calc.finished.connect(self.finishThread)

        self.tableWidget_jobList.clearContents()
        self.tableWidget_jobList.itemClicked.connect(self.job_clicked)
        self.tableWidget_jobList.itemDoubleClicked.connect(self.job_doubleclicked)

        return

    def __readsettings(self):

        # 検索範囲時刻の初期値設定
        # とりあえず直近1カ月範囲？
        # 開始時刻は現在時刻より１カ月前
        defaultstartdate = QDateTime.currentDateTime()
        lastmonth = defaultstartdate.addMonths(-1)

        self.dateTimeEdit_start.setDateTime(lastmonth)
        #終了時刻はなう
        self.dateTimeEdit_end.setDateTime(defaultstartdate)
        self.reload_clicked()

        # iniから前回設定読み出して自動選択とかをこの辺にそのうち
        # とりあえず空にしとくか
        self.comboBox_UserName.clearEditText()
        self.comboBox_ProjectName.clearEditText()

        self.tableWidget_jobList.setRowCount(0)
        # Commentとか直接使用しない列もあるから、列増えるたびに要調整。。
        self.tableWidget_jobList.setColumnCount(16)
        #QDateTime to ISODate String....
        #print(defaultstartdate.toString(QtCore.Qt.ISODate))

        return

    def __writesettings(self):
        pass

    def __makelistfromqcombo(self,combobox):
        itemlist = []
        for i in range(combobox.count()):
            itemlist.append(combobox.itemText(i))
        itemlist.reverse()
        return itemlist

    # jobサーチ開始
    def search_clicked(self):

        #print("search_clicked")

        # if self.dateTimeEdit_start
        # if self.dateTimeEdit_end

        # 増えてきたら何がしかリセット関数にまとめないとダメかもなあ。
        self.tableWidget_jobList.setSortingEnabled(False)
        self.tableWidget_jobList.clearContents()
        self.checkedcount = 0

        self.calc.reset()

        #beforedate
        #QDateTime -> ISO8601String -> python datetime
        beforedate = dateutil.parser.parse(self.dateTimeEdit_start.dateTime().toString(QtCore.Qt.ISODate))
        enddate = dateutil.parser.parse(self.dateTimeEdit_end.dateTime().toString(QtCore.Qt.ISODate))

        # チェック範囲矛盾？
        if(beforedate > enddate):
            #エラー処理はそのうち良い感じに
            errstr = "Invalid date.\nbefore = " + str(beforedate) + "\nend = " + str(enddate)
            self.msgBox.setText(errstr)
            #self.msgBox.setInformativeText(self.calc.errmessage)
            self.msgBox.setStandardButtons(QtGui.QMessageBox.Ok)
            self.msgBox.exec_()
            return

        self.__setEnabled(False)

        self.calc.setOpt(self.calc.STARTDATE,beforedate)
        self.calc.setOpt(self.calc.ENDDATE,enddate)

        if self.tabWidget_Comannds.currentIndex():
            # ジョブID指定モードだね
            self.calc.setOpt(self.calc.RUNMODE, self.calc.RUNMODE_SEARCH_JOBID)

            #idlist = str(self.plainTextEdit_jobID.toPlainText()).split(u'2029')
            idlist = str(self.plainTextEdit_jobID.toPlainText()).split('\n')
            #pp.pprint(idlist)
            self.calc.setOpt(self.calc.JOBIDS, idlist)

        else:
            self.calc.setOpt(self.calc.RUNMODE, self.calc.RUNMODE_SEARCH_INQ)
            if self.comboBox_UserName.currentText():
                self.calc.setOpt(self.calc.USER_NAME,str(self.comboBox_UserName.currentText()))
            # else:
            #     self.calc.setOpt(self.calc.USER_NAME,u"")

            if self.comboBox_ProjectName.currentText():
                self.calc.setOpt(self.calc.PROJ_NAME,str(self.comboBox_ProjectName.currentText()))

        self.beginTimer()
        self.calc.start()

        return

    # 単価計算開始
    def calc_clicked(self):
        #print("calc_clicked")

        if self.tableWidget_jobList.rowCount() == 0:
            return

        # 係数値を拾うよん。未入力=1として扱う。
        if self.lineEdit_keisuu.text():
            try:
                keisuu = float(self.lineEdit_keisuu.text())

            except Exception as ex:
                errstr = "Error:Invalid Value.\n" + str(ex)
                self.msgBox.setText(errstr)
                # self.msgBox.setInformativeText(self.calc.errmessage)
                self.msgBox.setStandardButtons(QtGui.QMessageBox.Ok)
                self.msgBox.exec_()
                return

            self.calc.setOpt(self.calc.CALC_KEISUU, keisuu)

        # 実働時間算出用の日時情報をリセット
        self.early_subdate = datetime.datetime(2100,12,31,23,59,59)
        self.late_enddate = datetime.datetime(1970,1,1)

        calc_list = [] # (jobid,コンカレントタスク数,チャンク数)のタプルのリスト
        userdict = {}  # プロジェクト名指定検索の時、関連するユーザを出力するための辞書
        for i in range(self.tableWidget_jobList.rowCount()):
            item = self.tableWidget_jobList.item(i,0)

            if item.checkState() == QtCore.Qt.Checked:
                jobid = self.tableWidget_jobList.item(i, 1).text()
                conc_task = int(self.tableWidget_jobList.item(i, 11).text())
                chunk = int(self.tableWidget_jobList.item(i,12).text())
                # プロジェクト範囲抽出を受けた時に関連ユーザ出すためにユーザ名だけこっそり抽出しておく
                username = str(self.tableWidget_jobList.item(i, 2).text()).split('_')[0]

                userdict[username] = username #key重複は上書き

                # print(item.text())
                wk_tuple = (jobid, conc_task, chunk)
                calc_list.append(wk_tuple)

                #v110 実働時間算出のため、すべての選択済みジョブの送信日時の一番早い時刻と終了時刻の一番遅い時刻を決定する
                wk_subdate = dateutil.parser.parse(self.tableWidget_jobList.item(i,5).text()).replace(tzinfo=None)
                if self.early_subdate > wk_subdate:
                    self.early_subdate = wk_subdate

                wk_enddate = dateutil.parser.parse(self.tableWidget_jobList.item(i,6).text()).replace(tzinfo=None)
                if self.late_enddate < wk_enddate:
                    self.late_enddate = wk_enddate


            # else:
            #     print("no check is " + str(self.tableWidget_jobList.item(i,0).text()))

        self.calc.setOpt(self.calc.JOBID_CONTASKS,calc_list)

        # サーチする時にプロジェクト名指定でサーチした？
        if self.calc.optdict.get(self.calc.PROJ_NAME):
            # 関連ユーザ抽出用に最終出力結果にユーザ一覧辞書を渡しておく
            self.calc.setOpt(self.calc.CALC_PROJUSER,userdict)

        self.calc.setOpt(self.calc.RUNMODE, self.calc.RUNMODE_CALC)
        #pp.pprint(wk_list)

        self.__setEnabled(False)
        self.beginTimer()
        self.calc.start()

        return

    def reload_clicked(self):

        # 通信失敗？
        if not self.calc.getUserandProject():
            #reload諦めよっと
            errstr = "Error: getUserandProject() Failed."
            self.msgBox.setText(errstr)
            self.msgBox.setInformativeText(self.calc.errmessage)
            self.msgBox.setStandardButtons(QtGui.QMessageBox.Ok)
            self.msgBox.exec_()
            sys.exit(-1)

        # 一回全部中身クリアする
        self.comboBox_UserName.clear()
        self.comboBox_ProjectName.clear()

        # ユーザ名とプロジェクト名一覧を設定
        # ユーザ名

        wk_list = []
        for key in self.calc.userdict:
            wk_list.append(key)

        # ABCそーとしよっと
        wk_list.sort()
        # ABCそーと順でコンボボックスに追加しよっと
        for user in wk_list:
            self.comboBox_UserName.addItem(user)

        wk_list[:] = []
        # プロジェクト名
        for key in self.calc.projdict:
            wk_list.append(key)

        # ABCそーとしよっと
        wk_list.sort()
        for project in wk_list:
            self.comboBox_ProjectName.addItem(project)

        self.comboBox_ProjectName.clearEditText()
        self.comboBox_UserName.clearEditText()

        self.status_label.setText("User and Project Reloaded.")

    # def closeEvent(self,cevent):
    #
    #     if not self.rpack.isRunning() or self.rpack.isFinished():
    #         self.__writesettings()
    #         cevent.accept()
    #     else:
    #         msgBox = QtGui.QMessageBox()
    #         msgBox.setIcon(QtGui.QMessageBox.Warning)
    #         msgBox.setWindowIcon(QtGui.QIcon(":/ico/" + self.appname + ".ico"))
    #         msgBox.setText(self.tr("RapidPack is running"))
    #         msgBox.setInformativeText(self.tr("Can't close RapidPack while pack end."))
    #         msgBox.setStandardButtons(QtGui.QMessageBox.Ok)
    #         msgBox.exec_()
    #         cevent.ignore()

    def calcclear_clicked(self):
        self.textEdit_Result.clear()

    def csvout_clicked(self):

        if self.tableWidget_jobList.rowCount() == 0:
            return

        dstdialog = QtGui.QFileDialog(self)
        dstdialog.setFileMode(QtGui.QFileDialog.AnyFile)
        dstdialog.setAcceptMode(QtGui.QFileDialog.AcceptSave)
        dt = QDateTime.currentDateTime()
        # prefix_name = self.appname
        # prefix_name += "_"
        prefix_name = dt.toString("yyyyMMddhhmmss")

        prefix_name += ".csv"

        writablepath = os.path.expanduser('~') + os.sep
        writablepath += prefix_name

        # print(writablepath)
        dststr = dstdialog.getSaveFileName(
            self,
            self.tr("input output filename."),
            writablepath
        )
        if not dststr[0]:
            return
        #print(dststr)
        self.__csvout(dststr)

        infostr = "CSV output finished."
        self.msgBox.setText(infostr)
        self.msgBox.setStandardButtons(QtGui.QMessageBox.Ok)
        self.msgBox.setIcon(QtGui.QMessageBox.Information)
        self.msgBox.exec_()

        self.msgBox.setIcon(QtGui.QMessageBox.Warning)

    def timerEvent(self,tevent):
        #print("timer! tevent = {0} selftimerid = {1}".format(tevent.timerId(),)
        if(tevent.timerId() == self.timerid and self.calc.message):
            replstr = self.calc.message
            dotstr = ""
            for i in range(0,self.dot_count):
                dotstr += "."

            self.status_label.setText(replstr + dotstr)
            if self.calc.errmessage:
                self.textEdit_Result.append(self.calc.errmessage)
                self.calc.errmessage = ""

        self.dot_count += 1
        if(self.dot_count == 4):
            self.dot_count = 0

    # def eventFilter(self,widget,event):
    #     if(event.type() == QtCore.QEvent.KeyPress):
    #         if(widget is self.comboBox_SourceDir):
    #             #print("source combo ignore")
    #             return True
    #         elif(widget is self.comboBox_OutputPath):
    #             #print("output combo ignore")
    #             return True
    #         elif(widget is self.textEdit_ignorefolders):
    #             #print("ignore folders ignore")
    #             return True
    #
    #     return super(MainWindow,self).eventFilter(widget,event)

    # @QtCore.Slot()
    def beginTimer(self):
        self.timerid = QObject.startTimer(self,1000)
        # print("begin timerid = {0}".format(self.timerid))

    # @QtCore.Slot()
    def stopTimer(self):
        # print("stop timerid = {0}".format(self.timerid))
        self.status_label.clear()
        QObject.killTimer(self,self.timerid)

    @QtCore.Slot()
    def beginTimer(self):
        self.timerid = QObject.startTimer(self,1000)
        # print("begin timerid = {0}".format(self.timerid))

    @QtCore.Slot()
    def stopTimer(self):
        # print("stop timerid = {0}".format(self.timerid))
        QObject.killTimer(self,self.timerid)

    @QtCore.Slot(str)
    def finishThread(self):

        self.stopTimer()

        # なんかエラーっぽいメッセージあったらとりあえず出力
        if self.calc.errmessage:
            self.textEdit_Result.append(self.calc.errmessage)
            self.calc.errmessage = ""

        # 処理内容ごとにあちこち振り分けかなー
        # レコードサーチの場合
        if self.calc.optdict[self.calc.RUNMODE] == self.calc.RUNMODE_SEARCH_INQ \
                or self.calc.optdict[self.calc.RUNMODE] == self.calc.RUNMODE_SEARCH_JOBID:

            # なんか1レコードでもあった？
            if len(self.calc.searchresultlist):
                self.__setrecord(self.calc.searchresultlist)
                self.__fitcolumns()
            else:
                # レコード0の時はメッセージ出したろかな。。

                errstr = "There are no jobs."
                self.msgBox.setText(errstr)
                self.msgBox.setIcon(QtGui.QMessageBox.Information)
                self.msgBox.setStandardButtons(QtGui.QMessageBox.Ok)
                self.msgBox.exec_()
                self.msgBox.setIcon(QtGui.QMessageBox.Warning)
                # self.label_job.setText("There are no jobs.")
                self.label_jobs.setText("There are no jobs.")

            self.status_label.setText('Search finished.')

        else:
            # 計算modeの場合は結果を出力

            # 各ジョブごとの金額をリストに反映
            for i in range(self.tableWidget_jobList.rowCount()):
                checkitem = self.tableWidget_jobList.item(i,0)
                jobid = self.tableWidget_jobList.item(i,1).text()

                # print(str(self.tableWidget_jobList.columnCount()))

                # 計算対象かつ、指定ジョブIDがキーとして存在するか
                if checkitem.checkState() == QtCore.Qt.Checked and \
                    jobid in self.calc.calcjobresultdict:
                    # item = QtGui.QTableWidgetItem(str(int(self.calc.calcjobresultdict[jobid])))
                    item = self.tableWidget_jobList.item(i, self.tableWidget_jobList.columnCount() - 2)
                    item.setText(self.calc.calcjobresultdict[jobid]['TotalTaskTime'])

                    item = self.tableWidget_jobList.item(i,self.tableWidget_jobList.columnCount() - 1)
                    item.setText(str(int(self.calc.calcjobresultdict[jobid]['JobPrice'])))

                    # self.tableWidget_jobList.setItem(i,self.tableWidget_jobList.columnCount() - 1,item)

            self.textEdit_Result.append("/-----------------------------------------------------/\n")

            earlysub_str = self.early_subdate.strftime("%Y/%m/%d %H:%M:%S")
            late_enddate_str = self.late_enddate.strftime("%Y/%m/%d %H:%M:%S")

            workdate = self.late_enddate - self.early_subdate

            self.textEdit_Result.append("WorkStartDate: %s\nWorkEndDate: %s" % (earlysub_str,late_enddate_str))
            self.textEdit_Result.append("Workingdays: %s\n" % self.calc.time_f(workdate.total_seconds()))
            #️ self.textEdit_Result.append("Workingdays: %s\n\n" % workdate)

            self.textEdit_Result.append(self.calc.calcresult)
            self.textEdit_Result.append("/-----------------------------------------------------/\n")
            self.calc.calcresult = ""
            self.status_label.setText('Calc finished.')
            self.__fitcolumns()

        # button類のロックを解除
        self.__setEnabled(True)
        # msgBox = QtGui.QMessageBox()
        # msgBox.setIcon(QtGui.QMessageBox.Warning)
        # msgBox.setWindowTitle(self.appname)
        # msgBox.setStandardButtons(QtGui.QMessageBox.Ok)

    @QtCore.Slot()
    def job_clicked(self,item):

        # print(item.checkState())
        # JobNameへのクリックにしか反応しないよ
        if item.column() == 0:
            if item.checkState() == QtCore.Qt.CheckState.Checked:
                self.checkedcount += 1
            else:
                self.checkedcount -= 1

            self.label_jobs.setText('%d total, %d checked' % (self.tableWidget_jobList.rowCount(), self.checkedcount))

    @QtCore.Slot()
    def job_doubleclicked(self,item):
        if item.column() == 13:
            outpathlist = item.text().split(',')
            for i in range(len(outpathlist)):

                if os.path.exists(outpathlist[i]):
                    QtGui.QDesktopServices.openUrl(outpathlist[i])
                else:
                    errstr = "warn:" + outpathlist[i] + " can't access.\n"
                    self.textEdit_Result.append(errstr)


    def __setrecord(self,resultlist):

        self.tableWidget_jobList.setRowCount(len(resultlist))

        # レコード数分降順でループ
        # deadline APIが必ずdate昇順でしか返してこないのを逆利用

        for i,rec in enumerate(reversed(resultlist)):
            #print(i)

            item = QtGui.QTableWidgetItem(rec['JobName'])
            # 先頭だけはちぇっかぶる
            # flags = QtCore.Qt.ItemIsUserCheckable
            # flags |= QtCore.Qt.ItemIsEnabled
            # print(int(item.flags()))
            # print(flags)

            item.setFlags(49) # (int)QtCore.Qt.ItemIsUserCheckable + (int)QtCore.Qt.ItemIsEnabled)

            # checkedの設定するよ
            if rec['Checked']:
                item.setCheckState(QtCore.Qt.Checked)
                self.checkedcount += 1
            else:
                item.setCheckState(QtCore.Qt.Unchecked)

            qfont = item.font()
            qfont.setPointSize(qfont.pointSize() + 1)
            qfont.setBold(True)
            item.setFont(qfont)

            self.tableWidget_jobList.setItem(i, 0,item)

            # JobID
            item = QtGui.QTableWidgetItem(rec['JobID'])
            qfont = item.font()
            qfont.setPointSize(qfont.pointSize() - 1)
            item.setFont(qfont)

            self.tableWidget_jobList.setItem(i, 1,item)
            # UserName
            item = QtGui.QTableWidgetItem(rec['UserName'])
            self.tableWidget_jobList.setItem(i, 2, item)

            # Status
            item = QtGui.QTableWidgetItem(rec['Status'])
            self.tableWidget_jobList.setItem(i, 3, item)

            # SubMachine
            item = QtGui.QTableWidgetItem(rec['SubMachine'])
            self.tableWidget_jobList.setItem(i, 4, item)
            # SubDate
            # item = QtGui.QTableWidgetItem(rec['SubDate'].isoformat())
            item = QtGui.QTableWidgetItem(rec['SubDate'].strftime("%Y/%m/%d %H:%M:%S"))
            self.tableWidget_jobList.setItem(i, 5, item)

            # FinDateとJobRenderTimeは'Failed'時は入れられないよん
            # print(rec['FinDate'])
            if rec['FinDate']:
                # FinDate
                item = QtGui.QTableWidgetItem(rec['FinDate'].strftime("%Y/%m/%d %H:%M:%S"))
                self.tableWidget_jobList.setItem(i, 6, item)
            else:
                item = QtGui.QTableWidgetItem("None")
                self.tableWidget_jobList.setItem(i, 6, item)

            # FramesList
            item = QtGui.QTableWidgetItem(rec['FramesList'])
            self.tableWidget_jobList.setItem(i, 7, item)

            # Framesそのうちparseしてそれっぽく処理しないといけないなー
            item = QtGui.QTableWidgetItem(rec['Frames'])
            self.tableWidget_jobList.setItem(i, 8, item)

            # Plugin
            item = QtGui.QTableWidgetItem(rec['Plugin'])
            self.tableWidget_jobList.setItem(i, 9, item)

            item = QtGui.QTableWidgetItem(rec['Comment'])
            self.tableWidget_jobList.setItem(i, 10, item)

            # Concurent_tasks
            item = QtGui.QTableWidgetItem(rec['ConcTasks'])
            self.tableWidget_jobList.setItem(i, 11, item)

            # Chunk
            item = QtGui.QTableWidgetItem(rec['Chunk'])
            self.tableWidget_jobList.setItem(i, 12, item)

            # OutDir
            item = QtGui.QTableWidgetItem(rec['OutDir'])
            self.tableWidget_jobList.setItem(i, 13, item)

            # TotalTaskTime
            item = QtGui.QTableWidgetItem("None")
            self.tableWidget_jobList.setItem(i, 14, item)

            # JobPrice
            item = QtGui.QTableWidgetItem("")
            self.tableWidget_jobList.setItem(i, 15, item)


            # 完全な正常終了以外はすべて色変更
            if rec['Status'] != 'Completed':
                # JobNameも色表示変更しておこかな
                # self.tableWidget_jobList.item(i, 0).setBackground(QtGui.QColor(255, 88, 71))
                # if rec['Status'] == 'Failed':
                #   item.setBackground(QtGui.QColor(255, 88, 71))
                self.__setColortoRow(self.tableWidget_jobList, i, QtGui.QColor(255, 160, 122))

        # とりあえず出力した結果を表示
        self.label_jobs.setText('%d total, %d selected' % (len(resultlist),self.checkedcount))

        # 1.0.4
        self.tableWidget_jobList.sortItems(5,QtCore.Qt.DescendingOrder)

    def __setEnabled(self,req_bool):
        self.pushButton_Search.setEnabled(req_bool)
        self.pushButton_Calc.setEnabled(req_bool)
        self.tableWidget_jobList.setEnabled(req_bool)

    def __setColortoRow(self,table,rowIndex,color):
        for j in range(table.columnCount()):
            table.item(rowIndex,j).setBackground(color)
            # self.tableWidget_jobList.item(rowIndex, j).

    def __csvout(self,outpath):

        # print(outpath)

        # ファイルオープン
        try:
            ofd = codecs.open(str(outpath[0]), 'w',encoding="shift_jis")

            for i in range(self.tableWidget_jobList.columnCount()):
                # print(self.tableWidget_jobList.horizontalHeaderItem(i).text())
                itemtext = "\"" + self.tableWidget_jobList.horizontalHeaderItem(i).text() + "\","
                ofd.write(itemtext)
            ofd.write("\n")

            for i in range(self.tableWidget_jobList.rowCount()):
                for j in range(self.tableWidget_jobList.columnCount()):


                    itemtext = "\"" + self.tableWidget_jobList.item(i, j).text() + "\""
                    # outpath情報には表示上の都合で','を除去
                    if(j == 13):
                        itemtext = itemtext.replace(',','')
                    if(j !=  self.tableWidget_jobList.columnCount() - 1):
                        itemtext += ","
                    else:
                        itemtext += "\n"
                    ofd.write(str(itemtext))

        except (IOError, OSError) as err:
            errstr = "Can't open " + outpath
            self.msgBox.setText(errstr)
            self.msgBox.setStandardButtons(QtGui.QMessageBox.Ok)
            self.msgBox.exec_()
            return

            ofd.close()

    def __fitcolumns(self):
        for i in range(self.tableWidget_jobList.columnCount()):
            # Commentは長くなることあるからそれ以外を表示しよっと。。
            if i == 10:
                pass
            if i == 13:
                self.tableWidget_jobList.setColumnWidth(i,120)
            else:
                self.tableWidget_jobList.resizeColumnToContents(i)

        self.tableWidget_jobList.setSortingEnabled(True)
        #   self.tableWidget_jobList.resizeRowsToContents()
