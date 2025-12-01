import React, { useState, useEffect } from 'react';
import { TextField, Button, Paper, Typography, Box, CircularProgress, Alert } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { baseUrl } from '../config';
import { LOGIN_ENDPOINT } from '../api/endpoints';
import { saveUserInfo } from '../utils/auth';

export default function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    console.log('[Login Debug] Component mounted');
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    console.log('[Login Debug] Form submitted', { username, password });
    setError('');
    if (!username || !password) {
      console.log('[Login Debug] Validation failed: missing username or password');
      setError('Please enter both username and password.');
      return;
    }
    setLoading(true);
    const url = `${baseUrl}${LOGIN_ENDPOINT}`;
    console.log('[Login Debug] Sending login request to backend:', url);
    try {
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
      });
      const data = await res.json();
      setLoading(false);
      if (res.ok && data.success) {
        saveUserInfo(data);
        console.log('[Login Debug] Login success, user info saved, redirecting to /home');
        navigate('/home');
      } else {
        console.log('[Login Debug] Login failed:', data.message || 'Invalid credentials');
        setError(data.message || 'Invalid username or password.');
      }
    } catch (err) {
      setLoading(false);
      console.log('[Login Debug] Network or server error:', err);
      setError('Network or server error.');
    }
  };

  return (
    <Paper elevation={3} sx={{padding:4, maxWidth:400, margin:'40px auto'}}>
      <Typography variant="h5" gutterBottom>Login</Typography>
      <Box component="form" noValidate autoComplete="off" onSubmit={handleSubmit}>
        <TextField label="Username" variant="outlined" fullWidth margin="normal"
          value={username} onChange={e => setUsername(e.target.value)} disabled={loading} />
        <TextField label="Password" type="password" variant="outlined" fullWidth margin="normal"
          value={password} onChange={e => setPassword(e.target.value)} disabled={loading} />
        {error && <Alert severity="error" sx={{mt:2}}>{error}</Alert>}
        <Button variant="contained" color="primary" fullWidth sx={{mt:2}} type="submit" disabled={loading}>
          {loading ? <CircularProgress size={24} /> : 'Login'}
        </Button>
      </Box>
    </Paper>
  );
}
