export default function StatusPanel({status,message,progress}:{status:"processing"|"error"|"success";message:string;progress?:number}) {
  return <div className={`status-panel ${status}`}><strong>{status==="processing"?"Processing":status==="success"?"Complete":"Something went wrong"}</strong><p>{message}</p>{status==="processing"&&<div className="progress"><span style={{width:`${progress??35}%`}}/></div>}</div>;
}
