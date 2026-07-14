export default function FileUpload({label,description,file,onChange,accept=".json,application/json",disabled=false}:{label:string;description:string;file:File|null;onChange:(file:File|null)=>void;accept?:string;disabled?:boolean}) {
  return <label className={`upload-card ${file?"has-file":""}`}>
    <input type="file" accept={accept} disabled={disabled} onChange={e=>onChange(e.target.files?.[0]??null)} />
    <span className="file-chip">{file ? "Selected" : "Upload"}</span>
    <strong>{label}</strong>
    <small>{file ? file.name : description}</small>
  </label>;
}
