from pathlib import Path
import json
from posixpath import dirname
import sys
import uuid
import shutil
import re
import zipfile, os

FULL_JSON_FILE="default_full_config.json"
# mergeSimpleJSON()函数用于合并base和fullData两个JSON字符串
# 函数只是把fullData上有的而base没有的key增加到base上。
# 要注意的是base是dict对象的指针，所以在函数中改变的base，同样也改变了调用者的参数
# 譬如在这个程序里，configs作为调用者的参数，同样被改变了，所以不需要return
def mergeSimpleJSON(base, fullData):
    for key in fullData:
        if base.get(key) is None:
            base[key]=fullData[key]
        else:
            if (isinstance(fullData[key],dict)):
                mergeSimpleJSON(base[key],fullData[key])

"""
关于ePub格式以及其包含文件的详细信息，请参阅：
https://www.hxa.name/articles/content/epub-guide_hxa7241_2007.html

txt->ePub转换器genePub.py安装后目录如下：
ls <安装目录>
genePub.py
templates/
    META-INF/
        container.xml: 这是ePub文件中用于指定content.opf位置的配置文件
    content_template.opf: 这个文件用于描述ePub文件中所包含的所有文件以及文件排序
    toc_template.ncx: 这个文件用于导航
    chapters_template.html: 这个文件是每个章节的标准模板，genePub.py会把每个章节输出为一个html文件。
    titlepage_template.xhtml: 这个文件是封面的模板
    navPoint_template.txt: 这个文件是嵌入到toc.ncx里面内容的模板，嵌入的内容是具体章节相关
    stylesheet.css: html格式模板
    page_styles.css: html页描述模板
    mimetype: ePub文件格式描述，一般不变
    default_full_config.json: 这个文件是全配置的JSON文件。关于配置文件，请参阅后面JSON格式解释
"""

# 检查程序所需要的文件是否齐全
progFilePath=Path(__file__)
templateRoot=progFilePath.parent / progFilePath.stem / 'templates'
if not templateRoot.exists():
    print("没有找到程序所需文件目录%s，程序安装不完全，请检查。"%(templateRoot.absolute()))
    quit()
try:
    fHandler=open((templateRoot / FULL_JSON_FILE),'r')
except FileNotFoundError:
    print ("在%s下面找不到全配置文件%s，程序安装不完全，请检查。"%(templateRoot.absolute(),FULL_JSON_FILE))
    quit()

try:
    full_configs=json.load(fHandler)
except json.JSONDecodeError as err:
    fHandler.close()
    print ("%s文件格式错误：%s"%str(err))
    print ("程序文件被修改过，请重新安装。")
    quit()
fHandler.close()
print ("全配置文件%s载入成功。"%(FULL_JSON_FILE))

mustHaveFileList=full_configs['FILE_TO_COPY'].copy()
for key in full_configs.get('TEMPLATE_FILES'):
    mustHaveFileList.append(full_configs['TEMPLATE_FILES'][key])

for filename in mustHaveFileList:
    filePath=templateRoot / filename
    if not filePath.exists():
        print ("在%s目录下面找不到文件%s，程序安装不完全，请检查。"%(templateRoot.absolute(),filename))
        quit()
print ("程序自带必要文件已经全部找到。")

# 本程序使用为：
# genePub.py [可选：json文件路径]
# 如果不带参数，则使用templates/default_full_config.json文件里面"json file name"的定义。
if len(sys.argv)>1:
    jsonFile=Path(sys.argv[1])
else:
    jsonFile=Path(full_configs.get('json file name'))

try:
    fHandler=open(jsonFile,'r')
except FileNotFoundError:
    print ("找不到配置文件%s，请检查文件是否存在。"%(jsonFile.absolute()))
    print("本程序使用为：")
    print("genePub.py [可选：json文件路径]")
    print("如果不带参数，则使用%s文件里面\"json file name\"的定义。"%((templateRoot / FULL_JSON_FILE)).absolute())
    quit()

try:
    configs=json.load(fHandler)
except json.JSONDecodeError as err:
    fHandler.close()
    print ("%s文件格式错误：%s"%str(err))
    quit()
fHandler.close()
print ("配置文件%s载入成功。"%(jsonFile.name))

# 融合配置文件和全配置文件
# 1. 把全配置文件里面有而输入的配置文件没有的键值填充到输入配置文件生成的json里面。
# 2. META-DATA里面的GENERATOR是'Program Name'+'v'+'Version'组成。
# 3. 生成UUID填入到configs['META-DATA']['UUID']中
# 4. 根据regex_strings的个数填入['META-DATA']['TOC_DEPTH']

mergeSimpleJSON(configs,full_configs)
configs['META-DATA']['GENERATOR']=configs['Program Name']+' v'+configs['Version']
configs['META-DATA']['UUID']=str(uuid.uuid4())
configs['META-DATA']['TOC_DEPTH']=str(len(configs['regex_strings']))
print ("配置融合成功。")

"""
fHandler=open("fullconfigs",'w',encoding='utf-8')
json.dump(configs,fHandler,ensure_ascii=False,indent=4)
fHandler.close()
"""

#获得输入txt文件路径
srcTxt=configs.get('src_txt')
if srcTxt is None or srcTxt=="":
    print ("配置文件缺少'src_txt'的定义！'src_txt'的作用是指定输入的txt文件路径。")
    exit()
srcPath=Path(srcTxt)
if not srcPath.exists():
    print ("输入txt文件'%s'不存在。"%(srcPath.absolute()))
    print("请检查JSON文件配置:", jsonFile.absolute())
    quit()
print ("使用输入txt文件：", srcPath.absolute())

#获取输出文件目录位置
outputPath=Path(configs['output_dir'])
if outputPath.exists():
    if any(outputPath.iterdir()):
        print ("输出目录%s不为空，请清理文件或者指定其他位置"%(outputPath.absolute()))
        quit()
else:
    try:
        outputPath.mkdir()
    except PermissionError as err:
        print ("用户对目录%s权限不足，不能创建输出目录%s。"%(outputPath.parent.absolute(),outputPath.absolute()))
        print ("详细出错信息：", str(err))
        quit()
print ("使用输出目录：", outputPath.absolute())

#获取章节题目的正则表达式
regStrings=configs.get('regex_strings').copy()
if not isinstance(regStrings,list):
    print("配置文件中'regex_strings'设置格式错误。")
    print ("配置文件里面的'regex_strings'格式为：[\"正则表达式1\", \"正则表达式2\",...]")
    quit()
else:
    if len(regStrings)==0 or regStrings[0]=="":
        print("JSON文件中关于'regex_strings'的设置不可以为空或者空字符串。")
        quit()

"""
counter=0
for s in regStrings:
    counter+=1
    print ("正则表达式#%d: %s"%(counter,s))
"""
# Copy非template的文件到输出目录
fileCopyList=configs['FILE_TO_COPY'].copy()
for fileName in fileCopyList:
    srcPath=templateRoot / fileName
    dstPath=outputPath / fileName
    if srcPath.is_file():
        if not dstPath.parent.exists():
            dstPath.parent.mkdir()
        shutil.copyfile(srcPath,dstPath)
        print ("文件\"%s\"copy成功。"%(srcPath.name))
    if srcPath.is_dir():
        shutil.copytree(srcPath,dstPath)
        print ("目录\"%s\"copy成功。"%(srcPath.name))

#读入所有template文件，并填充META-DATA
file2Gen=configs['TEMPLATE_FILES'].copy()
for key in configs['TEMPLATE_FILES']:
    srcPath=templateRoot / configs['TEMPLATE_FILES'][key]
    fHandler=open(srcPath,'r')
    file2Gen[key]=fHandler.read()
    fHandler.close()
    for metaDataKey in configs['META-DATA']:
        placeHolder="[%s]"%(metaDataKey)
        file2Gen[key]=file2Gen[key].replace(placeHolder,configs['META-DATA'][metaDataKey])
    
"""
    saveFile=outputPath / key
    fHandler=open(saveFile,'w')
    fHandler.write(file2Gen[key])
    fHandler.close()
    print ("文件%s保存成功。"%(key))
"""

#处理小说的文本文件
fHandler=open(srcTxt,'r')
txtLines=fHandler.readlines()
fHandler.close()

navPointStr="" #toc.ncx文件中嵌入部分[NAV_POINTS]
manifestStr="" #content.opf文件中嵌入部分[MANIFEST_ITEMS]
spineStr="" #content.opf文件中嵌入部分[SPINE_ITEMS]
manifestItemTemplate=configs['TEMPLATE_STRINGS']['manifest_item']
spineItemTemplate=configs['TEMPLATE_STRINGS']['spine_item']
chapterIndex=0
chapterContent=''
lastTitle=''
isTitle=False
lineCounts=len(txtLines)

for counter, line in enumerate(txtLines):
    print ("\r正在处理：%d/%d"%(counter+1,lineCounts),end=" ")
    if line.strip()=="":
        if counter==lineCounts-1:
            print("到达最后一行。")
        else:
            continue
    for regPattern in configs['regex_strings']:
        matchObj=re.match(regPattern, line)
        if matchObj:
            isTitle=True
            if lastTitle=="":
                lastTitle=configs['Chapter0']
            break
    if (not isTitle) and counter!=lineCounts-1:
        chapterContent+='    <p>'+line.strip()+'</p>\n'
    else:
        if chapterContent=='' and lastTitle=='': #这个情况是输入的txt文件一开头就是第一章
            lastTitle=line
            print ("开头就是章节名，没有%s"%(configs['Chapter0']))
            continue
        if counter==lineCounts-1:
            chapterContent+='    <p>'+line.strip()+'</p>\n'
        chapterContent=file2Gen['chapters.html'].replace('[CHAPTER_CONTENT]',chapterContent)
        chapterContent=chapterContent.replace('[CHAPTER_TITLE]', lastTitle)
        chapterFileName=configs['chapter file prefix']+str(chapterIndex)+'.html'

        #处理章节相关的content.opf嵌入部分
        pageID=configs['chapter file prefix']+str(chapterIndex)
        manifestStr+=manifestItemTemplate.replace('[PAGE_ID]', pageID) \
            .replace('[PAGE_FILE]', chapterFileName)
        spineStr+=spineItemTemplate.replace('[PAGE_ID]', pageID)
        #完成content.opf嵌入部分

        #处理章节相关的toc.ncx嵌入部分
        navPointStr+=file2Gen['toc_navPoint'].replace('[NAV_ID]', pageID)\
            .replace('[PLAYORDER]', str(chapterIndex+1))\
                .replace('[CHAPTER_TITLE]', lastTitle)\
                    .replace('[CHAPTER_FILE]', chapterFileName)
        #完成toc.ncx嵌入部分

        chapterPath=outputPath / chapterFileName
        fHandler=open(chapterPath,'w')
        fHandler.write(chapterContent)
        fHandler.close()
        #print ("第%d章%s完成，输出文件%s"%(chapterIndex,lastTitle,chapterPath.name))
        lastTitle=line.strip()
        chapterIndex+=1
        chapterContent=""   
        isTitle=False
print ("文件总共%d行"%(lineCounts))

#生成titlepage.xhtml
fHandler=open(outputPath / 'titlepage.xhtml','w')
fHandler.write(file2Gen['titlepage.xhtml'])
fHandler.close()

#生成content.opf
opfStr=file2Gen['content.opf'].replace('[MANIFEST_ITEMS]',manifestStr)\
    .replace('[SPINE_ITEMS]',spineStr)
fHandler=open(outputPath / 'content.opf', 'w')
fHandler.write(opfStr)
fHandler.close()
print ("content.opf生成成功。")

#生成toc.ncx
tocStr=file2Gen['toc.ncx'].replace('[NAV_POINTS]', navPointStr)
fHandler=open(outputPath / 'toc.ncx', 'w')
fHandler.write(tocStr)
fHandler.flush()
fHandler.close()
print ("toc.ncx生成成功。")

"""
for rootDir, dirs, fileNames in os.walk(outputPath):
    for name in fileNames:
        delFileName=Path(rootDir) / name
        print ("Deleting %s..."%(str(delFileName)))
        os.remove(delFileName)
    
for rootDir, dirs, fileNames in os.walk(outputPath):    
    for dirName in dirs:
        delDirName=Path(rootDir) / dirName
        print("Deleting %s..."%(str(delDirName)))



time.sleep(3)
"""

print ("正在生成epub文件")
zipFileName=configs['META-DATA']['BOOK_NAME']+'.epub'

with zipfile.ZipFile(zipFileName, 'w', zipfile.ZIP_STORED) as f:
    for i in os.walk(outputPath):
        for n in i[2]:
            joinStr=''.join((i[0],'/',n))
            regstr=outputPath.name+r'[/\\]'
            acnameStr=re.sub(regstr, '', joinStr)
            #print("i[1]%s      acnames=%s"%(i[1],n))
            f.write(joinStr,acnameStr)
f.close()
print ("epub文件生成成功。")


print ("正在删除源文件。。。")
shutil.rmtree(outputPath)
print ("完成删除。")
