/*
 * Copyright 2013 miguel, Javier Herrera Grupo de Sistemas Inteligentes (GSI UPM) 
 *                                         <http://gsi.dit.upm.es>
 *
 *  Licensed under the Apache License, Version 2.0 (the "License");
 *  you may not use this file except in compliance with the License.
 *  You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 *  Unless required by applicable law or agreed to in writing, software
 *  distributed under the License is distributed on an "AS IS" BASIS,
 *  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 *  See the License for the specific language governing permissions and
 *  limitations under the License.
 */
package maia.client;

import jason.RevisionFailedException;
import jason.asSyntax.Literal;

import java.io.BufferedReader;

import java.io.IOException;
import java.io.InputStreamReader;
import java.net.URI;
import java.net.URISyntaxException;

import maia.start;
import maia.client.MaiaClientAdapter;
import maia.client.annotation.OnMessage;
import maia.utils.JSONUtils;
import java.util.logging.*;

import jason.asSemantics.*;

/**
 * <b>Project:</b> maia-client<br />
 * <b>Package:</b> maia.client<br />
 * <b>Class:</b> MaiaClient.java<br />
 * <br />
 * <i>GSI 2013</i><br />
 *
 * @author Miguel Coronado (miguelcb@gsi.dit.upm.es)
 * @version	Jun 3, 2013
 *
 */
public class MaiaRxClient extends MaiaClientAdapter {
	
	
    private Logger logger = Logger.getLogger("gui."+maia.start.class.getName());
    private String username;
    TransitionSystem ts;

    /**
     * @param serverURI
     * @throws URISyntaxException 
     * @throws RevisionFailedException 
     */
    public MaiaRxClient(String serverURI, final TransitionSystem tas) throws URISyntaxException, RevisionFailedException {
        super(new URI(serverURI));     
        ts = tas;
        ts.getLogger().info("Empiezo a suscribirme en Maia...");
		
    }

    @OnMessage("subscribed")
    public void onSubscribe(String message) {
    	
        ts.getLogger().info("Subscribed >> " + message + "\n");
        ts.getLogger().info("Ya me han suscrito!");
    }
    
    
    @OnMessage("username::accepted")
    public void getUsername(String message) {
    	
        this.username = JSONUtils.getDataName(message);
        //ts.getLogger().info("Me han puesto de username: " + this.username);
        //ts.getLogger().info("Username give:" + this.username);
    }
    
    @OnMessage("message")
    public void message(String message) {
    	
        String content = JSONUtils.getDataName(message);
        String origin = JSONUtils.find(message, "origin");
        String nfact = "";
        String nuser = "";
        if (origin != null && origin.equals(this.username)) {
            return;
        }
      //ts.getAg().addBel(Literal.parseLiteral("sol_internet(si)"));

        //Evitar que se afirmen los mensajes cs_
        int intIndex = content.indexOf("[sendcs]");
        if(intIndex != - 1){
        	//ts.getLogger().info("era para ChatScript...");
        	return;
        }
        

        
        
        
        //Discard action if message not asking to assert a fact
        if (!content.contains( "assert")){
            return;
        }
        
        ts.getLogger().info("Tengo un mensaje!");
        ts.getLogger().info("Recibido >> " + content );
      
        //Sample accepted message: [assert explained( concept dowhile ) ] [user Javi]
      
      
        //Extract new fact to assert from the Maia message
        nfact=content.substring(content.indexOf("[assert")+8, content.indexOf("]" ));
        nfact=nfact.replace("concept ","concept_");
        nfact=nfact.replace(" ","");
        nfact=nfact.replace("-","");
        
        nuser=content.substring(content.indexOf("[user")+6, content.lastIndexOf("]" ));
        
        nfact+="[user(\""+nuser+"\")]";
        

        
        ts.getLogger().info("Afirmando "+nfact);
    	try {
    		ts.getAg().delBel(Literal.parseLiteral(nfact));
			ts.getAg().addBel(Literal.parseLiteral(nfact));
		} catch (RevisionFailedException e) {
			ts.getLogger().info("Error a�adiendo belief "+nfact);
		}
    	
    	
    	
    	
    }
    
    public static void main (String[] args) throws URISyntaxException, InterruptedException, IOException {
        

        
    }
    
}
