import React, { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import axios from 'axios'

const ExecutionView = ({ showToast }) => {
  const { sessionId } = useParams()
  const navigate = useNavigate()
  
  const [status, setStatus] = useState('starting')
  const [error, setError] = useState(null)
  const [pauseScreenshot, setPauseScreenshot] = useState(null)
  const [otpValue, setOtpValue] = useState('')
  const [events, setEvents] = useState([])
  
  const pollInterval = useRef(null)

  useEffect(() => {
    startPolling()
    return () => {
      if (pollInterval.current) clearInterval(pollInterval.current)
    }
  }, [sessionId])

  const startPolling = () => {
    if (pollInterval.current) clearInterval(pollInterval.current)
    
    pollInterval.current = setInterval(async () => {
      try {
        const res = await axios.get(`/sessions/${sessionId}`)
        const sessionData = res.data.data
        
        const currentStatus = sessionData.status
        setStatus(currentStatus)
        
        if (currentStatus === 'paused_captcha' || currentStatus === 'paused_otp') {
          if (sessionData.pause_screenshot) {
            setPauseScreenshot(sessionData.pause_screenshot)
          }
        }
        
        if (currentStatus === 'completed' || currentStatus === 'failed') {
          clearInterval(pollInterval.current)
          if (currentStatus === 'failed') {
            setError(sessionData.error || 'Execution failed')
          }
        }
      } catch (err) {
        console.error('Polling error', err)
      }
    }, 2000)
  }

  const handleResumeCaptcha = async () => {
    try {
      await axios.post(`/sessions/${sessionId}/resume`, { type: 'captcha' })
      setStatus('running')
      showToast('Resuming execution...', 'info')
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to resume')
    }
  }

  const handleResumeOtp = async () => {
    if (!otpValue.trim()) {
      setError('Please enter OTP')
      return
    }

    try {
      await axios.post(`/sessions/${sessionId}/resume`, { 
        type: 'otp', 
        otp: otpValue 
      })
      setStatus('running')
      setOtpValue('')
      showToast('OTP submitted, resuming...', 'info')
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to submit OTP')
    }
  }

  return (
    <div className="view active">
      <div className="page-container" style={{maxWidth:'600px', margin:'0 auto', paddingTop:'2rem'}}>
        <div className="execution-header" style={{textAlign:'center', marginBottom:'2rem'}}>
          <h2>
            {status === 'running' && 'Filling form on your behalf...'}
            {status === 'completed' && 'Form Submitted Successfully!'}
            {status === 'failed' && 'Something went wrong'}
            {status === 'paused_captcha' && 'CAPTCHA detected - solve manually'}
            {status === 'paused_otp' && 'OTP required - enter below'}
            {status === 'starting' && 'Starting automation...'}
          </h2>
          
          <div style={{marginTop:'1rem', fontSize:'1.2rem', fontWeight:'bold', color:'#007bff'}}>
            Status: {status}
          </div>
        </div>

        {status === 'paused_captcha' && (
          <div className="glass-card" style={{textAlign:'center'}}>
            <div style={{fontSize:'3rem', marginBottom:'1rem'}}>🤖</div>
            <h3>CAPTCHA Detected</h3>
            <p style={{marginBottom:'1.5rem'}}>Please solve the CAPTCHA in the automated browser window.</p>
            
            {pauseScreenshot && (
              <div style={{margin:'1rem 0'}}>
                <img src={`http://localhost:8000${pauseScreenshot}`} alt="CAPTCHA Screenshot" style={{maxWidth:'100%', borderRadius:'8px', border:'1px solid #ccc'}} />
              </div>
            )}
            
            <button onClick={handleResumeCaptcha} className="btn btn-primary" style={{width:'100%'}}>
              I solved it - continue
            </button>
          </div>
        )}

        {status === 'paused_otp' && (
          <div className="glass-card" style={{textAlign:'center'}}>
            <div style={{fontSize:'3rem', marginBottom:'1rem'}}>📱</div>
            <h3>OTP Required</h3>
            <p style={{marginBottom:'1.5rem'}}>Enter the verification code sent to your phone or email.</p>
            
            <div style={{display:'flex', gap:'10px', justifyContent:'center'}}>
              <input
                type="text"
                value={otpValue}
                onChange={(e) => setOtpValue(e.target.value)}
                placeholder="000000"
                maxLength={6}
                style={{padding:'10px', fontSize:'1.2rem', width:'150px', textAlign:'center', borderRadius:'8px', border:'1px solid #ccc'}}
              />
              <button onClick={handleResumeOtp} className="btn btn-primary">
                Submit OTP
              </button>
            </div>
          </div>
        )}

        {error && (
          <div className="glass-card" style={{borderLeft:'4px solid #dc3545', background:'#f8d7da'}}>
            <h3 style={{color:'#dc3545', marginTop:0}}>Error Detail</h3>
            <p>{error}</p>
          </div>
        )}

        {status === 'completed' && (
          <div className="glass-card" style={{textAlign:'center', background:'#d4edda', borderLeft:'4px solid #28a745'}}>
            <div style={{fontSize:'3rem', marginBottom:'1rem'}}>✅</div>
            <h3>All done!</h3>
            <p style={{marginBottom:'1.5rem'}}>Your form has been successfully completed.</p>
            <button onClick={() => navigate('/dashboard')} className="btn btn-primary">
              Return to Dashboard
            </button>
          </div>
        )}

        {status === 'failed' && (
          <div style={{marginTop:'2rem', textAlign:'center'}}>
            <button onClick={() => navigate('/dashboard')} className="btn btn-secondary" style={{marginRight:'10px'}}>
              Go Home
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

export default ExecutionView
