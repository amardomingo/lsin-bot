# coding=utf-8

from bottle import route, run, request, response
from socket import socket
from re import sub

import os, inspect, unicodedata
import urllib,urllib2,json
import websocket
import thread
import time
import argparse
import re
import logging
import pyunitex_emb

this_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))    
response.content_type = 'application/json'


#ChatScript variables
cs_buffer_size = 1024
cs_tcp_ip = '127.0.0.1'
cs_tcp_port = 1024
facts_dir="facts/"
cs_facts_dir = this_dir+"/../ChatScript/"+facts_dir


#Maia server variables
maia_uri = '127.0.0.1:1337'


#Logging system
log_name='gsibot'
logger = logging.getLogger(log_name)
hdlr = logging.FileHandler(this_dir+'/'+log_name+'.log')
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
hdlr.setFormatter(formatter)
logger.addHandler(hdlr) 
logger.setLevel(logging.INFO)
logging.basicConfig(level=logging.DEBUG, format='%(message)s')

@route('/')
def rootURL():
    return TalkToBot()  
    
    
    
@route('/TalkToBot') 
def TalkToBot():
    
    feedback=request.query.feedback or '0'
    if (feedback != '0'):
        saveFeedback()
        return;
    
    
    #Collect URI parameters
    query_q = request.query.q
    query_user = request.query.user or 'anonymous'
    query_bot = request.query.bot or 'Duke'
    query_lang = request.query.lang or 'es'
    
    full_response = '0' #Default values
    
    
    #Send user input to Unitex, get response    
    unitex_output = sendUnitex(query_user, query_q, query_bot, query_lang)   

    #Split Unitex out-of-band commands and not identified contents
    unitex_output_array= splitOOB(unitex_output)
    cs_input = unitex_output_array[-1]  

    
    #Send user input to ChatScript, get response
    cs_output = sendChatScript(cs_input, query_bot, query_user) 
    
    
    #Split conversation response and out-of-band commands (example: Hello again [sendmaia assert returning])
    cs_output_array = splitOOB(cs_output)
    
    #Extract the natural language response from the array
    nl_response = cs_output_array[0]
    cs_output_array.pop(0);
    
    sefarad_response = ""
    #Proceed with further executions if needed, getting the natural language response produced
    for command in cs_output_array:
        resp=executeOOB(command,query_user,query_bot);  
        nl_response+= resp[0]
        if resp[1] != "":
           sefarad_response+=resp[1]

    #Detect the @full_response flag used to ask the user for feedback
    if '@fullresponse' in nl_response:
        full_response= '1'
        nl_response=re.sub("@fullresponse","",nl_response)

    #Render natural language response in JSON format
    response = renderJson(query_q, nl_response, query_bot, query_user, full_response, sefarad_response)
    print response
    return response

    

def saveFeedback():

    log_text="feedback using bot '"+request.query.bot+"' in question '"+request.query.q+"' with answer given '"+request.query.response
    
    if (request.query.feedback=='2'):
        logger.error("Negative "+log_text)
    else:
        logger.info("Positive "+log_text)

    

#Produces an array with the natural language response as first element, and OOB tags the rest
def splitOOB(s):
    
    response_array = []
    response_array.append(re.sub('\[[^\]]*\]','',s))
    oob_array = re.findall('\[[^\]]*\]',s)
    
    for command in oob_array:
        response_array.append(command)
        
    return response_array;

#Executes the out-of-band commands and returns the natural language response produced   
def executeOOB(content,usr,bot):

    nl_response=""
    sefarad_reponse = ""
    while ("[" in content):
        
        if (("[sendmaia" not in content) and ("[updatekb" not in content) and ("[sendcs" not in content)) and (("[sendSefarad" not in content)):
            logger.error("OOB with execution not found: "+content)
            content=""
            
        if "[sendmaia" in content:
            logger.error("Ignoring maia")
            content=""
        if "[sendSefarad" in content:
            content, sefarad_response = sendSefarad(content)
        if "[updatekb" in content:
            content=updateCsKb(content,bot,usr)
        
        if "[sendcs" in content:
            cs_output=sendChatScript(content,bot,usr) 
            cs_output_array=splitOOB(cs_output)
            nl_response+=cs_output_array[0] 
            cs_output_array.pop(0);
            content=""
            for command in cs_output_array:
                content+=command;   

    return (nl_response, sefarad_response)

def sendSefarad(content):
    print content
    content = content.replace('[', '')
    content = content.replace(']', '')
    content = content.replace('sendSefarad ', '')
    sefarad_response = ' {'
    print content
    for pair in content.split(','):
        key_value = [val.strip() for val in pair.split(':')] 
        print key_value
        if key_value[0] == 'concepto':
            sefarad_response+= '"concept":'+'"'+key_value[1]+'"'
        elif key_value[0] == 'filter':
            sefarad_response += ', "filter": { "' + key_value[1] + '":'
        elif key_value[0] == 'value':
            sefarad_response += '"' +key_value[1] + '" }'
    sefarad_response+= '}'
    
    print sefarad_response
    return "", sefarad_response

#Sends an input to Unitex to process it
def sendUnitex(user, query, bot, lang):

    logger.info("Unitex input: "+query)
    
    #Remove special characters, lower case letters
    query = sub('["\'¿¡!?@#$]', '', query)
    query = query.lower()
    removeacc = ''.join((c for c in unicodedata.normalize('NFD',unicode(query)) if unicodedata.category(c) != 'Mn'))
    query=removeacc.decode()
    
    
    #Process the input using Unitex
    u = pyunitex_emb.Unitex()
    response_string=""

    bufferDir =this_dir+"/../Unitex/unitex_buffer"
    commonDir= this_dir +"/../Unitex/common_resources"
    botDir = this_dir + "/../Unitex/bot_resources/" + bot
    delaDir=commonDir+"/lang_dictionary/es/delaf.bin" 
    dicoDir=commonDir+"/lang_dictionary"
    botDir_dics = botDir+"/dictionary"

    txt_name=user
    txt=bufferDir+"/"+txt_name+".txt"
    snt=bufferDir+"/"+txt_name+".snt"
    snt_dir=bufferDir+"/"+txt_name+"_snt"
    txt_output=bufferDir+"/"+txt_name+"_o.txt"
    
    text_file = open(txt, "w")
    text_file.write(query)
    text_file.close()
    
    if not os.path.exists(snt_dir): os.makedirs(snt_dir)
    u.Convert("-s","UTF8",txt,"-o",txt+"2")
    u.Normalize(txt+"2","-r",commonDir+"/Norm.txt","-qutf8-no-bom")
    u.Convert("-s","UTF8",snt,"-o",snt+"2")
    u.Tokenize(snt+"2","-a",commonDir+"/alphabet/"+lang+"/Alphabet.txt")
    bot_dicos = []

    os.chdir(botDir_dics)
    for files in os.listdir("."):
        if files.endswith(".bin"):
            bot_dicos=bot_dicos+[botDir_dics+"/"+files]
            

    paramsDico= ["-t",snt,"-a",commonDir+"/alphabet/"+lang+"/Alphabet.txt"] + bot_dicos
    u.Dico(*paramsDico)
    paramsLocate=["-t",snt,botDir+"/graph/main_graph.fst2","-a",commonDir+"/alphabet/"+lang+"/Alphabet.txt","-L","-R","--all","-b","-Y","-m",";".join(bot_dicos)]
    u.Locate(*paramsLocate)
    u.Concord(snt_dir+'/concord.ind','-m',txt_output,"-qutf8-no-bom")
    
    with open(txt_output, 'r') as f:
        response_string=response_string+f.next()
            

    logger.info("Unitex output: "+response_string)
    return response_string

#Sends an input to ChatScript to process it
def sendChatScript(query, bot, user):

    
    if "[sendcs" in query:
        query = re.sub('sendcs ','',query)
        query = re.sub('\[','',query)
        query = re.sub('\]','',query)   
        query = re.sub('\(','[',query)
        query = re.sub('\)',']',query)  
    
    logger.info("ChatScript input: "+query)
    #Remove special characters and lower case
    query = sub('["\'¿¡@#$]', '', query)
    query = query.lower()
    removeacc = ''.join((c for c in unicodedata.normalize('NFD',unicode(query)) if unicodedata.category(c) != 'Mn'))
    query=removeacc.decode()
    bot = bot.lower()


    #Message to server is 3 strings-   username, botname, message     
    socketmsg = user+"\0"+bot+"\0"+query 

    s = socket()
    try:
        s.connect((cs_tcp_ip, cs_tcp_port))
        s.send(socketmsg)
        data = s.recv(cs_buffer_size)
        s.close()
        
    except socket.error, e:
        logger.error("Conexion a %s on port %s failed: %s" % (address, port, e))
        data = "ChatScript connection error"

    logger.info("ChatScript output: "+data)
    return data

#Updates the ChatScript knowledge base
def updateCsKb(content,bot,usr):    

    if "[updatekb]" in content:
        content=re.sub("\[updatekb\]","",content)

    if bot=="Duke":
        kbase="java"
    else:
        kbase="global"
    
    logger.info("Updating ChatScript knowledge base kb-"+kbase)
    
    cskbfile = cs_facts_dir+"kb-"+kbase 
    newcontent="" 
    content_array = json.loads(content)
    
    #Remove special characters and lower case label
    content_array["label"]=re.sub("-","",content_array["label"])
    content_array["label"]=content_array["label"].lower()

    #Add the new contents to the ChatScript kb file
    for ritem in content_array:
        if ritem != "label" and ritem != "links_to":
            content=re.sub(" ","_",content_array[ritem])
            newcontent+= "\n( "+content_array["label"]+" "+ritem+" "+content+" )"
        
        if ritem == "links_to":
                for sritem in content_array["links_to"]:
                    label=re.sub("-","",sritem["label"])
                    label=label.lower()
                    newcontent+= "\n( "+content_array["label"]+" links_to "+label+" )"

    with open(cskbfile, 'a') as f:
        f.write(newcontent) 
    

    return "[sendcs (import "+facts_dir+"kb-"+kbase+" "+content_array["label"]+")]"
    
#Renders the response in Json
def renderJson(query, response, bot, user, fresponse, sefarad_response):
    response = response.replace('"', '\\"')
    result = '{"dialog": {"sessionid": "'+user+'", "user": "'+user+'", "bot": "'+bot+'", "q": "'+query+'", "response": "'+response+'", "test": "General Saludo", "url": "nul", "flashsrc": "../flash/happy.swf", "full_response": "'+fresponse+'", "state": "happy", "mood": "happy"'
    if sefarad_response != "":
        result+= ', "sefarad": '+sefarad_response
    result+=' }}'
    return result

    
#Maia functions

#Sends a message to the Maia network
def sendMaia(msg,bot,usr):

    if "[sendmaia " in msg:
        msg = re.sub('sendmaia ','',msg)

    
    logger.info("Sending message to the Maia network: "+msg)
        
    websocket.enableTrace(False)
    ws = websocket.WebSocketApp("ws://"+maia_uri,
                                on_message = on_message,
                                on_error = on_error,
                                on_close = on_close)                    
    ws.send_type = 'message'
    ws.send_data = msg + " [user "+usr+"]"
    ws.subscribe = 'message' #lista a suscribirse
    ws.on_open = on_open
    ws.response=''
    ws.run_forever()
    
    maia_output=ws.response
    
    #Check if message is for this user, wait if not
    while ("[user" in maia_output):     
        output_user=maia_output[maia_output.find("[user")+6 : maia_output.find("]", maia_output.find("[user"))]
        
        if (usr==output_user):          
            maia_output = maia_output[0: maia_output.find("[user")]

        else:
            print "Waiting Maia response for user..."+ws.response
            time.sleep(1)
            ws.response = maia_output
        
    logger.info("Received and accepted from Maia: "+ maia_output)
    return maia_output #Respuesta
    
#Triggered when received a Maia message
def on_message(ws, message):
    mymsg = json.loads(message)
    
    #Accept only messages with an [actuator]
    if (('[' in mymsg['data']['name']) and ('[assert' not in mymsg['data']['name']) and ('[retrieve' not in mymsg['data']['name']) ):
        ws.response = mymsg['data']['name']
        print ">> Received: %s" % mymsg['data']['name']
        ws.close()
    

def on_error(ws, error):
    logger.error(error)

def on_close(ws):

    ws.send('{"name":"unsubscribe","data": {"name" : "%s"}}' % ws.subscribe);
    time.sleep(2)
    ws.close()
    
def on_open(ws):
    ws.send('{"name":"username","data": {"name": "%s"}}' % "python_client");
    time.sleep(1);
    ws.send('{"name":"subscribe","data": {"name" : "%s"}}' % ws.subscribe);
    time.sleep(2)
    logger.info('Sending to Maia {"name":"message","data": {"name" : "%s"}}' % ws.send_data)
    ws.send('{"name":"message","data": {"name" : "%s"}}' % ws.send_data)    
    time.sleep(1)
    thread.start_new_thread(run, ())

if __name__ == '__main__':
    run(host='localhost', port=8090, debug=True)
