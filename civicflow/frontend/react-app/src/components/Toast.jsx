import React from 'react'

import { CheckCircle, XCircle, AlertTriangle, Info, X } from 'lucide-react'

const Toast = ({ message, type = 'info', onClose }) => {
  const icons = {
    success: <CheckCircle size={16} />,
    error: <XCircle size={16} />,
    warning: <AlertTriangle size={16} />,
    info: <Info size={16} />
  }

  return (
    <div className={`toast ${type}`}>
      <span className="toast-icon">{icons[type]}</span>
      <span className="toast-message">{message}</span>
      <button className="toast-close" onClick={onClose}><X size={16} /></button>
    </div>
  )
}

export default Toast
