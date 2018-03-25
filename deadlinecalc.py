# -*- coding: utf-8 -*-

import os
import shutil
import platform
import sys

import inspect
import binascii

from PySide.QtCore import QObject
from PySide import QtCore
from PySide import QtGui

import pprint as pp
import Deadline.DeadlineConnect as Con

import dateutil.parser
import math

sysisDarwin = platform.system() == 'Darwin'
sysisWindows = platform.system() == 'Windows'

class DeadLineCalc(QtCore.QThread,QObject):

    __version__ = "1.1.2"
    APPNAME = "DeadlineCalc"

    sig_appendtext = QtCore.Signal(str,bool)
    sig_appendtext_unit = QtCore.Signal(str,object)
    sig_updstatus  = QtCore.Signal(str)
    sig_progress = QtCore.Signal(int)
    sig_showdialog = QtCore.Signal(dict)

    sig_begintimer = QtCore.Signal()
    sig_stoptimer  = QtCore.Signal()

    Debugdir = "Debug"

    DIV_HOUR = 3600         # ノード時間単価から秒単位単価算出する際の基準値
    STARTDATE = "STARTDATE" # 時刻指定で抽出する時の開始時刻(ここから) ENDと同時指定されない場合はENDを現在時刻として扱うよ
    ENDDATE = "ENDDATE"     # 時刻指定で抽出する時の終了時刻(ここまで) STARTが指定されない場合は1970くらいとして扱う

    USER_NAME = "USERNAME"  # 案件名文字列 '個人名_案件名'の'個人名'のほうね
    PROJ_NAME = "PROJNAME"  # 案件名文字列 '個人名_案件名'の'案件名'のほうね

    RUNMODE   = "RUNMODE"   # スレッドrunする時に何やるの？モードフラグ
    RUNMODE_SEARCH_INQ = "INQ"   # runはジョブ一覧出力をUSER名またはPROJ名で抽出するモードだよ
    RUNMODE_SEARCH_JOBID  = "ID"    # runはジョブ一覧出力を指定ジョブIDから出すモードだよ
    RUNMODE_CALC       = "CALC"  # runはジョブ一覧から単価計算する算出モードだよ

    JOBIDS = "JOBIDS"              # ジョブIDのリスト
    JOBID_CONTASKS = "JOBID_TASKS" # ジョブIDとタスクの同時実行起動数がセットになったタプルのリスト
                                   # (str,int)
    CALC_KEISUU = "KEISUU"         # 各レンダーノードの単価にかける掛け率(小数 )
    CALC_PROJUSER = "PROJUSER"     # 当該プロジェクトに関係するユーザ名の辞書 key:ユーザ名,value:ユーザ名
                                   # 'sawatsu_hogeproj' の場合は左のhogeがキーとバリューよん


    DEADLINE_IP = '192.168.0.148'  # DEADLINE SERVERのIP
    # DEADLINE_PORT = 8083          # DEADLINE webserviceのポート番号 <- DEADLINE8
    DEADLINE_PORT = 8082           # DEADLINE webserviceのポート番号 <- DEADLINE10
    DEADLINE_STAT_COMPLETED_JOB = 3    # job['Stat']の中身。"Completed"のこと
    DEADLINE_STAT_FAILED_JOB = 4       # job['Stat']の中身。"Failed"のこと
    DEADLINE_STAT_COMPLETED_TASK = 5  # task['Stat']の中身。"Completed"のこと,jobとなんで違うのん:(
    DEADLINE_STAT_FAILED_TASK = 6  # task['Stat']の中身。"Failed"のこと,jobとなんで違うのん。。:(

    GETSTATUS_TARGET = ['Completed','Failed'] # 'GetJobsInStates'に渡す用のターゲット状態文字列リスト

    # Statコード->文字列辞書
    GETSTATUS_REP = {str(DEADLINE_STAT_COMPLETED_JOB): 'Completed', \
                     str(DEADLINE_STAT_FAILED_JOB): 'Failed'}

    def __init__(self, parent=None):

        super(DeadLineCalc, self).__init__(parent)

        self.startdate = "" # ジョブ検索するときの検索範囲情報、開始時刻 # (datetime型)
        self.enddate   = "" # ジョブ検索するときの検索範囲情報、終了時刻 # (datetime型)

        self.nodeinfo = {}  # ノード単価情報辞書 key=スレーブ名,value=当該スレーブの秒単位金額(3600で割った後の値ね)
        self.optdict = {}   # オプション設定辞書 key=オプション名,value=いろいろ

        self.userdict = {}  # ユーザ名辞書 key=ユーザ名,value=ユーザ名
        self.projdict = {}  # 案件名辞書   key=案件名,value=案件名
        self.slavedict = {} # 各スレーブ情報辞書、key = スレーブ名,valueは以下の辞書
                            # {'Price'      : float 秒あたりの単価(exinfo9 / 3600ね)
                            #  'Tasklmt'    : int 当該スレーブのタスクリミット
                            #  'Totalprice' : int レンダー合計単価}

        self.searchresultlist = [] # ジョブサーチ出力結果をメインウインドウに渡す用データリスト
                                   # 中身は辞書で並びは先頭から時刻の古い順っぽいけど保証はないよ。
                                   #
                                   # { 'JobName': job["Props"]["Name"],  ジョブ名
                                   #   'JobID'  : job["_id"]           ,  ジョブID
                                   #   'UserName': job["Props"]["User"], ユーザ名(ex:gaku_misumisou)
                                   #   'Status'  : job["Stat"],          ジョブのステータス
                                   #   'SubMachine': job["Mach"],        ジョブ投入マシン名
                                   #   'SubDate': job["Date"],           ジョブ投入時刻(送信開始時刻)
                                   #   'FinDate': job["DateComp"]        ジョブ完了時刻
                                   #   'FramesList': job['FramesList']   フレーム範囲情報('0-100'or'10-12,8,6,4'みたいなばらばら値)
                                   #   'Frames'    : ↑を良い感じにparseした値だけど、う'torus_test_v1’形式のパースまんどくせ。。
                                   #   'Plugin'    : job['Plug']         アプリケーション名称
                                   #   'Checked'   : True or False       当該レコードをcheckedするかしないかフラグ
                                   #   'ConcTasks' : job['Props']['Conc'] 同時実行タスク数(jobに設定されてる方ね)
                                   #   'Chunk'     : job['Props']['Chunk'] チャンク数
                                   #   'OutDir'    : job['OutDir'] レンダリング結果の出力先フォルダパス(当該クライアント依存だよ)


        self.calcresult = ""       # 単価計算した合計額とかの最終出力が入ってる文字列バッファ
        self.calcjobresultdict = {}    # 各ジョブの合計金額辞書。key=ジョブID, value=辞書で中身はこんなん
                                       #    { 'JobPrice' : int, 当該ジョブのタスクの合計金額
                                       #      'TotalTaskTime' : int, 当該ジョブにかかったタスクの合計時間(通算秒?)

        self.con = 0        # Deadlineサーバとのコネクションハンドル
        self.message = ''   # calc内の状態をmainwindowに通知する用の文字列バッファ
        self.errmessage = ''# calc内のエラー状態をmainwindowに通知する用の文字列バッファ

    def reset(self):

        self.searchresultlist = []
        self.calcresult = ""
        self.calcjobresultdict = {}
        self.optdict = {}

        # if self.debuglog:
        #     filepath = os.path.join(self.dochome, self.Debugdir)
        #     # DebugDirなければ作成
        #     if not os.path.exists(filepath):
        #         os.mkdir(filepath)
        #
        #     filepath = os.path.join(filepath, self.starttime.strftime("debug_%Y%m%d_%H%M%S") + ".txt")
        #
        #     try:
        #         self.debugfd = open(filepath, 'wt', encoding="utf-8")
        #         #self.__debugwrite("test")
        #         self.__debugwrite(str(self.__dict__))
        #
        #     except OSError as oserr:
        #         print("self.debugfd open failed err={0}".format(str(oserr)))
        #         self.sig_appendtext("self.debugfd open failed err={0}".format(str(oserr)),False)
        #         #msgBox = QtGui.QMessageBox()
        #         #msgBox.setIcon(QtGui.QMessageBox.Warning)
        #         #msgBox.setText(self.tr("DebugLog write failed. path = {0} err={1}").format(filepath, str(oserr)))
        #         #msgBox.setStandardButtons(QtGui.QMessageBox.Ok)
        #         #msgBox.exec_()

    def setOpt(self,key,value):
        """
        各種オプション設定をする。
        :param key: オプション設定
        :param value: 設定値(型はキー名ごとにいろいろだよ)
        :rtype:  bool
        :return: 常にオプションセット成功/上書きやで
        """
        self.optdict[key] = value
        return True

    def connectServer(self):
        try:
            self.con = Con.DeadlineCon(self.DEADLINE_IP,self.DEADLINE_PORT)
        except Exception as e:
            self.errmessage = str(e) + "\nIP:" + self.DEADLINE_IP + "\nPORT:" + str(self.DEADLINE_PORT)
            return False
        return True

    # ユーザ名を良い感じにパースして記憶しとく
    def getUserandProject(self):

        try:
            wk_userlist = self.con.Users.GetUserNames()
        except Exception as e:
            self.errmessage = str(e)
            return False

        for userandproj in wk_userlist:

            # sawatsu_misumisouとか'_'で区切られてるのでパース
            parsed = userandproj.split('_',1)

            # パースしても長さが変わらない？ = ユーザ名のみのユーザだね
            if(len(parsed) == 1):
                # ユーザ名辞書だけに入れとく
                self.userdict[parsed[0]] = parsed[0]

            # パースしたら２個に分離した＝正常
            elif(len(parsed) == 2):
                self.userdict[parsed[0]] = parsed[0]
                self.projdict[parsed[1]] = parsed[1]

            else:
                # _が２つ以上あるのはとりあえず後ろを連結して表示する。
                self.userdict[parsed[0]] = parsed[0]
                self.projdict[parsed[1]] = parsed[1]

        return True

    def getSlaveInformation(self):

        self.slavedict.clear()

        try:
            slavelist = self.con.Slaves.GetSlaveNames()

            for slavename in slavelist:
                #print("slavename:" + slavename)
                slaveinfo = self.con.Slaves.GetSlaveInfoSettings(slavename)

                # Ex9に価格情報が入っていない場合はメッセージ出力してスキップ
                if not slaveinfo['Settings']['Ex9']:
                    self.errmessage += ("Warn:" + slavename + " Ex9 value is empty.\n")
                    continue

                slave_innerdict = {}

                # 係数設定あり？
                if self.optdict.get(self.CALC_KEISUU):
                    new_keisu = float(slaveinfo['Settings']['Ex9']) * self.optdict.get(self.CALC_KEISUU)
                    new_keisu = new_keisu / self.DIV_HOUR
                    slave_innerdict['Price'] = new_keisu
                else:
                    # 係数設定ないから単純に3600で秒単価求めちゃうよん
                    slave_innerdict['Price'] = float(slaveinfo['Settings']['Ex9']) / self.DIV_HOUR

                slave_innerdict['Tasklmt'] = slaveinfo['Settings']['TskLmt']
                slave_innerdict['Totalprice'] = 0

                self.slavedict[slavename] = slave_innerdict
                #pp.pprint(slaveinfo)
                #print(slavename)
                #pp.pprint(self.slavedict[slavename])

        except Exception as e:
            self.errmessage = "Error:getSlaveInformation\n" + str(e)
            return False

        #print("slavedict:")
        #pp.pprint(self.slavedict)
        return True


    def run(self):

        #print("run")
        #print("self.optdict:")
        #pp.pprint(self.optdict)

        # self.reset()
        # とりあえずジョブ一覧取るか
        # self.sig_begintimer.emit()

        # 処理する処理ごとに関数振り分ける感じかのう。。

        if self.optdict[self.RUNMODE] == self.RUNMODE_SEARCH_INQ \
             or self.optdict[self.RUNMODE] == self.RUNMODE_SEARCH_JOBID:

            try:
                self.message = "Getting Jobs"
                # 成功したジョブをひとまずすべて抽出,Library側に抽出機能ナインダヨネー。。
                joblist = self.con.Jobs.GetJobsInStates(self.GETSTATUS_TARGET)

            except Exception as e:
                self.errmessage = "Error:GetJobsInState\n" + str(e)
                return

            #user一覧それっぽく出力
            # pp.pprint(self.userdict)
            self.__make_searchresult(joblist)

        # self.calc.RUNMODE_CALC
        else:
            self.message = "Getting Slave Information"

            #スレーブ情報を入手
            if not self.getSlaveInformation():
                # 内部でerrmessageは設定済み
                return

            self.message = "Calculating"
            self.__calc_price(self.optdict[self.JOBID_CONTASKS])


    #deadline APIから受けとったjobリストをsearchresultlistにコピる前に対象レコード判定する
    def __make_searchresult(self,joblist):

        for job in joblist:

            # jobID直接指定の場合はこっちの専用ルートでいいよな。。
            # if jobid直接指定？
                # if self.jopiddict[self.JOBID] in job['_id']
                # 良い感じにレコード作ってcontinueする

            if self.optdict[self.RUNMODE] == self.RUNMODE_SEARCH_JOBID:
                # 指定ジョブIDとマッチするかな？
                #pp.pprint(self.optdict[self.JOBIDS])
                if str(job['_id']) in self.optdict[self.JOBIDS]:
                    # マッチするのでレコード出力しよかな
                    self.__make_search_record(job)
                continue
            # 取得したジョブが'Completed'でもないし、'Failed'でもない。
            if job['Stat'] != self.DEADLINE_STAT_COMPLETED_JOB and job['Stat'] != self.DEADLINE_STAT_FAILED_JOB:
                # 集計対象外なんでさっさと次いくよ
                continue

            # 当該ジョブの送信時刻取得
            # 終了時刻だと、ジョブがFailedのものの時に値入ってこないから、しぶしぶ送信時刻にする。
            # 1.1.1で開始時刻から送信時の時刻で抽出するように変更
            jobstarttime = dateutil.parser.parse(job['Date']).replace(tzinfo=None)

            # 当該ジョブの開始時刻は指定開始時刻より遅く、かつ終了時刻より早い？
            if (self.optdict[self.STARTDATE] < jobstarttime and \
                    self.optdict[self.ENDDATE] > jobstarttime):
                #print("_id:" + job['_id'] + ' DateComp: ' + job['DateComp'])

                # ユーザ名かプロジェクト名どっちかが指定されてる＝抽出を行う？
                if self.optdict.get(self.USER_NAME) or self.optdict.get(self.PROJ_NAME):
                    # print("username search enabled")
                    # 抽出のためにユーザ名パースするよ
                    job_userproj = job["Props"]["User"].split('_',1)

                    # ユーザ名_プロジェクト名　の形式が正しくない奴はそもそも抽出対象外
                    if len(job_userproj) > 2:
                        # print(job["Props"]["User"] + " exclude.")
                        continue

                    # ユーザ名とプロジェクト名両方を指定してる？
                    if self.optdict.get(self.USER_NAME) and self.optdict.get(self.PROJ_NAME):
                        # ユーザ名部分一致かつプロジェクト名部分一致？
                        # job_userproj[-1]は'_'がないユーザ名のみユーザ対策ね
                        if self.optdict.get(self.USER_NAME) in job_userproj[0] \
                            and self.optdict.get(self.PROJ_NAME) in job_userproj[-1]:
                            # print(self.optdict[self.USER_NAME] + '_' + self.optdict[self.PROJ_NAME] + " in " + job["Props"]["User"])
                            self.__make_search_record(job)
                    # ユーザ名のみ？
                    elif self.optdict.get(self.USER_NAME) and self.optdict.get(self.USER_NAME) in job_userproj[0]:
                        # print(self.optdict[self.USER_NAME] + " in " + job["Props"]["User"])
                        self.__make_search_record(job)

                    # プロジェクト名のみ？
                    elif self.optdict.get(self.PROJ_NAME) and self.optdict.get(self.PROJ_NAME) in job_userproj[-1]:
                        # print(self.optdict[self.PROJ_NAME] + " in " + job["Props"]["User"])
                        self.__make_search_record(job)
                    else:
                        # ありえないので何もしない
                        continue
                else:
                    # そもそも抽出条件なにもなし = 全抽出
                    # 変な名前の奴もとりあえず出しておくか。。
                    self.__make_search_record(job)

    # deadline APIから受けとったsearch対象確定済みのjobをsearchresultlistに良い感じに格納するよ
    # 格納対象かどうかは上位で判定してね
    def __make_search_record(self,job):

        rec_dict = {} # 1レコードのdict
        rec_dict['JobName'] = job["Props"]["Name"]
        rec_dict['JobID'] = job["_id"]
        rec_dict['UserName'] = job["Props"]["User"]
        rec_dict['Status'] = self.GETSTATUS_REP[str(job["Stat"])]
        rec_dict['SubMachine'] = job["Mach"]
        # Deadlineから取得したデータはtimezone付きでマイクロ秒がくっついてきて邪魔なので削っておく。
        rec_dict['SubDate'] = dateutil.parser.parse(job["Date"])

        if rec_dict['Status'] != 'Failed':
            rec_dict['FinDate'] = dateutil.parser.parse(job["DateComp"])
        else:
            rec_dict['FinDate'] = None

        # FrameListは文字列そのままで扱うよ
        # v112
        rec_dict['FramesList'] = job["Props"]["Frames"]
        rec_dict['Frames'] = self.__get_Frames(job["Props"]["Frames"])
        rec_dict['Plugin'] = job["Plug"]
        rec_dict['Comment'] = job["Props"]["Cmmt"]

        if str(job["Props"]["Dept"]).upper() == 'NG':
            # NG
            rec_dict['Status'] = rec_dict['Status'] + '(NG)'
            rec_dict['Checked'] = False
        elif str(job["Props"]["Dept"]).upper() == 'TEST':
            # TESTの場合にはチェックボックス外しておくよ
            rec_dict['Status'] = rec_dict['Status'] + '(TEST)'
            rec_dict['Checked'] = False
        elif rec_dict['Status'] == 'Failed':
            # Failedの場合もチェックボックス外しておくよ
            rec_dict['Checked'] = False
        else:
            # Completedだね
            rec_dict['Checked'] = True

        # 当該ジョブの同時実行数
        rec_dict['ConcTasks'] = str(job['Props']['Conc'])

        # 当該ジョブのチャンク数
        rec_dict['Chunk'] = str(job['Props']['Chunk'])

        # 当該ジョブの結果出力先フォルダ
        # だいたい先頭みたいだけどどうかなあ。。
        #pp.pprint(job['OutDir'])
        if isinstance(job['OutDir'],list):
            outdirstr = ""
            if job['OutDir'] == None:
                rec_dict['OutDir'] = ''
            else:
                for i in range(len(job['OutDir'])):
                    # print(str(i) + ":" + str(job['OutDir'][i]))
                    if(i == len(job['OutDir']) - 1):
                        outdirstr += str(job['OutDir'][i])
                    else:
                        outdirstr += str(job['OutDir'][i]) + ","

            rec_dict['OutDir'] = outdirstr
        else:
            # print("str:" + job['OutDir'])
            if not job['OutDir']:
                rec_dict['OutDir'] = ''
            else:
                rec_dict['OutDir'] = str(job['OutDir'])

        self.searchresultlist.append(rec_dict)
        # pp.pprint(job)


    def __calc_price(self,id_conctuples):

        total_rendertime = 0 # calc対象の全タスクの合計レンダリング時間(秒)
        total_frame = 0      # calc対象の全タスクの合計フレーム数

        job_rendertime = 0   # calc対象のジョブID単位の合計レンダリング時間(秒)

        # ジョブIDぶんまわすよ
        for jobid,conctask,chunk in id_conctuples:


            # 当該ジョブID単位の情報初期化
            # ジョブID単位の結果辞書生成
            jobcalcdict = {}
            # self.calcjobresultdict['JobPrice'] = 0
            # self.calcjobresultdict['TotalTaskTime'] = 0
            jobcalcdict['JobPrice'] = 0
            totaltasktime = 0

            #Jobを構成するタスク群を拾うよ
            try:
                tasks = self.con.Tasks.GetJobTasks(jobid)
            except Exception as e:
                self.errmessage = "Error:GetJobTasks\n" + str(e)
                return False

            for task in tasks['Tasks']:

                #1秒間あたりの料金取得
                if not self.slavedict.get(task['Slave']):
                    # 当該スレーブが有効(Ex9が入ってないまたはdeadline上に登録されてないスレーブ)
                    #
                    if task['Slave'] == u'':
                        slavestr = 'None!!'
                    else:
                        slavestr = task['Slave']
                    errstr = "Warn: jobid = " + jobid + " taskid = " + task['_id'] + " slavename = " + slavestr + "\n"
                    errstr += "skipped this job calc. skip tasknum = " + str(len(tasks['Tasks'])) + "\n"
                    self.errmessage += errstr
                    continue

                # 当該タスクがFailedの場合は当該タスクを計算対象としない。
                if task['Stat'] == int(self.DEADLINE_STAT_FAILED_TASK):
                    # print("pass:" + task['Frames'] + " " + str(task['Stat']))
                    continue

                #　'Comp' = 当該タスクが終了した時刻
                #  'StartRen' = 当該タスクの素材？を受信し終わった時刻
                #  'Start' = 当該タスクが素材を受信してないけど、指示を受けとった時刻
                #  素材転送時間も含む時間を利用時間として計算する
                enddate = dateutil.parser.parse(task['Comp'])
                # 素材転送開始時刻を取得
                startdate = dateutil.parser.parse(str(task['Start']))
                # Complete時刻 - 素材転送開始時刻 = Render Timeだよ
                timedelta = enddate - startdate

                # レンダー時間は小数点以下強制切り上げにしちゃうよ。計算早くなるし。。
                render_sec = math.ceil(timedelta.total_seconds())

                # 総レンダリング時間を加算
                total_rendertime += render_sec
                # ジョブ単位の情報の方に加算
                totaltasktime += render_sec

                # フレーム数取得
                # '1-1'とかで必ず入ってるっぽい。csv的なのもくるかもだけどとりあえず考えない。
                # frames = str.split(str(task['Frames']), '-')
                # framenum = int(frames[1]) - int(frames[0]) + 1
                framenum = int(self.__get_Frames(task['Frames']))

                total_frame += framenum

                # 当該タスクのチャンク数が1以上？(1タスクで数フレーム処理？)
                # if(chunk > 1):
                #     # 当該タスクが最終タスクだったりで、チャンク数きっかりのフレーム数じゃない？
                #     # このまま計算すると３フレのレンダリング時間＊３フレームで３倍になってしまうので、
                #     # レンダリング時間を１フレあたりのレンダリング時間に変更
                #     render_sec = render_sec / framenum

                # div_proc = 0
                # # ジョブ側の並列起動数が1より大きい？
                # if (conctask > 1):
                #     # スレーブの同時起動可能数がジョブの同時可能起動数よりおおきい？
                #     if (self.slavedict[task['Slave']]['Tasklmt'] >= conctask):
                #         # ジョブ並列起動の数はジョブ単位の起動数に制約するよ
                #         div_proc = conctask
                #     else:
                #         # ジョブ単位起動数に制約されないので、スレーブの並列数に従うよ
                #         div_proc = self.slavedict[task['Slave']]['Tasklmt']
                # else:
                #     # そもそも1
                #     div_proc = 1

                # v104まで
                # render_price = ((self.slavedict[task['Slave']]['Price'] * render_sec) / div_proc) * framenum

                # v105から
                render_price = (self.slavedict[task['Slave']]['Price'] * render_sec)

                # slave単位金額デバッグ
                #print('Slave:' + task['Slave'] + ' price_sec:' + str(self.slavedict[task['Slave']]['Price']) + ' Frame:' + \
                #      str(framenum) + ' RenderTime:' + str(render_sec) + ' Price:' + str(render_price))

                # slaveごとの合計金額に加算
                self.slavedict[task['Slave']]['Totalprice'] += render_price

                # jobごとの合計金額に加算
                # self.calcjobresultdict[jobid] += render_price
                jobcalcdict['JobPrice'] += render_price

            jobcalcdict['TotalTaskTime'] = self.time_f(totaltasktime)
            # job単位合計情報を格納
            self.calcjobresultdict[jobid] = jobcalcdict


            # jobid単位でばっぐ
            # print("jobid:" + jobid + " TotalPrice:" + str(self.calcjobresultdict[jobid]))

        # job->taskの数分全部回しきったので合計だすよん

        total_price = 0

        # 各Slaveごとにたまった料金合計をしていくだよ
        for key,value in self.slavedict.items():
            # print("slave:" + key + " total:" + str(value['Totalprice']))
            total_price += value['Totalprice']

        # self.calcresult += "/-----------------------------------------------------/\n"

        # v111で廃止
        # self.calcresult += "StartDate: %s\nEndDate: %s\n" % (self.optdict[self.STARTDATE],self.optdict[self.ENDDATE])

        # サーチする時にプロジェクト名指定で絞ってた場合はプロジェクト名と参加メンバを表示
        if self.optdict.get(self.PROJ_NAME):
            self.calcresult += "Project : %s\n" % self.optdict[self.PROJ_NAME]
            projstaff_len = len(self.optdict[self.CALC_PROJUSER])
            self.calcresult += "Staff: %d" % projstaff_len

            if projstaff_len:
                self.calcresult += "("
                for key in self.optdict[self.CALC_PROJUSER]:
                    self.calcresult += "%s " % key
                self.calcresult += ")\n"

        self.calcresult += "Total Jobs: %d\nTotal Task Render Time: %s\nTotal Frames: %d\n\nTotal Render price: %d yen\n" \
                            % (len(id_conctuples),self.time_f(total_rendertime),total_frame,total_price)
        # self.calcresult += "/-----------------------------------------------------/\n"

    # deadline APIから渡されるフレームリスト文字列を良い感じにパースしてフレーム数として返すよ
    def __get_Frames(self,frameliststr):
                                 # 前提入力はこんなん
                                 # '1-1'(ふれめ)
                                 # '1-10,11-20,21-30,35,36'
                                 # '-18'
                                 # '-20,-21,-22--30'
                                 # u'-'がU+2212でハイフンと区別されるけど、deadlineはハイフン(0x2d)だった。。
        parse_csvlist = []       # csvパースされた各フレーム範囲のリスト

        # print(frameliststr.encode('hex'))

        # とりあえずカンマパース
        parse_csvlist = frameliststr.split(',')
        framecount = 0

        for framerange in parse_csvlist:

            # print(framerange)
            parse_hyphenlist = framerange.split('-')

            if(len(parse_hyphenlist) == 1):

                # フレーム一個だけなんでminもmaxも同じ
                frame_min = parse_hyphenlist[0]
                frame_max = parse_hyphenlist[0]

            elif(len(parse_hyphenlist) == 2):

                if parse_hyphenlist[0] is u'':
                    # '-10'とかの単フレームだな
                    # フレーム番号一個だけなんでminもmaxも同じ
                    frame_min = parse_hyphenlist[1]
                    frame_max = parse_hyphenlist[1]
                else:
                    # '10-20' みたいなデータのはず
                    frame_min = parse_hyphenlist[0]
                    # parse_hyphenlist[1] はたぶん''(None)
                    frame_max = parse_hyphenlist[1]

            # カンマパースした中身に'-'が1個以上ある = '-20 - -1' みたいなデータ？
            else:
                # もうちょっと中を見ないと判定できねえ
                for framenum in parse_hyphenlist:

                    # '-20 - -1' の真ん中の-とか、パースすると空になるっぽいのでチェック
                    if framenum is u'':
                        continue
                    else:
                        # 先に見つかった方をとりあえずminとして扱うつもりだったけど
                        # '-20 - -10'みたいなのが来てもたぶん大丈夫かな。。
                        frame_min = framenum
                        frame_max = framenum

            # とりあえず二つのフレームは確定してるよ
            frame_min_int = 0
            frame_max_int = 0

            # print("frame_min = " + frame_min + " frame_max = " + frame_max)

            try:
                # 表示順逆転とかに対応する。'200-100'とかもありえるかなって。。
                frame_min_int = abs(int(frame_min))
                frame_max_int = abs(int(frame_max))

                if frame_min_int > frame_max_int:
                    #minとmax逆にするよ
                    wk_int = frame_min_int
                    frame_min_int = frame_max_int
                    frame_max_int= wk_int

                framecount = framecount + ((frame_max_int - frame_min_int) + 1)

            except ValueError as ve:
                print(ve)
                framecount = 99999999 #異常値扱いね
                break

        return(str(framecount))

    # 通算秒をintで渡すと"dd:hh:mm:ss"を日付文字列で返してくれるよ
    def time_f(self,secs):

        pos = abs(int(secs))
        day = pos / (3600*24)
        rem = pos % (3600*24)
        hour = rem / 3600
        abshour = float(pos) / 3600
        rem = rem % 3600
        mins = rem / 60
        secs = rem % 60
        res = '%dd %02d:%02d:%02d (%.1fh)' % (day, hour, mins, secs, abshour)
        if int(secs) < 0:
            res = "-%s" % res
        return res


if __name__ == '__main__':
    import sys
    # import Deadlinecalc_rc       #こいつを消すとリソースファイル読めなくなるので消しちゃダメよ
    from PySide import QtGui
    from PySide import QtCore
    from mainwindow import MainWindow

    app = QtGui.QApplication(sys.argv)

    # if (QtCore.QLocale.system().language() == QtCore.QLocale.Japanese):
    #     translator = QtCore.QTranslator()
    #     translator.load(":/qm/RapidPack_ja_JP.qm")
    #     app.installTranslator(translator)

    window = MainWindow()

    window.show()
    if sysisDarwin:
        window.raise_()
    sys.exit(app.exec_())