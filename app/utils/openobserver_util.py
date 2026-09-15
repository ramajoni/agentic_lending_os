import base64, json
import requests
 

class OpenObserver:
    def __init__(self,username : str , password : str, host : str, port : str):
        self.bas64encoded_creds = "Basic " + base64.b64encode(f"{username}:{password}".encode()).decode()
        self.observer_host = host
        self.observer_port = port
        self.observer = f"{self.observer_host}:{self.observer_port}"

    def ingest_log(self,data : dict):
        try:
            headers = {"Content-type": "application/json", "Authorization": self.bas64encoded_creds}
            org = "default"
            stream = "GuardPoc"
            openobserve_host = self.observer
            openobserve_url = openobserve_host + "/api/" + org + "/" + stream + "/_json"
          
            res =  requests.post(openobserve_url, headers=headers, data=json.dumps(data))
            print(res.text)
            
        except Exception as e:
            print(e.__str__())
            
