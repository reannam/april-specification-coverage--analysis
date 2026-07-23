import { DownloadIcon } from "../ui/Icons";
import { getDownloadUrl } from "../../services/api";
export default function DownloadCard({title,filename,url}:{title:string;filename?:string|null;url?:string|null}) {
  if (!url) return null;
  return <a className="download-card" href={getDownloadUrl(url)} download={filename??undefined}><span><DownloadIcon/></span><div><strong>{title}</strong><small>{filename??"Download file"}</small></div></a>;
}
