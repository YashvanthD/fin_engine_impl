import React, { useState } from 'react';
import { TextField, Button, Paper, Typography, Box } from '@mui/material';
import { apiFetch } from '../utils/api';

export default function Register() {
  const [form, setForm] = useState({ username: '', email: '', password: '', company_name: 'TaskCircuit', master_password: '' });
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const handleChange = (e) => {
    setForm(f => ({ ...f, [e.target.name]: e.target.value }));
  };
  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    if (!form.company_name) {
      setError('Company name is required');
      return;
    }
    if (!form.master_password) {
      setError('Master password is required');
      return;
    }
    try {
      const submitBody = { ...form };
      const res = await apiFetch('/auth/signup', {
        method: 'POST',
        body: JSON.stringify(submitBody),
        headers: { 'Content-Type': 'application/json' }
      });
      const data = await res.json();
      if (res.ok && data.success) {
        setSuccess('Registration successful!');
      } else {
        setError(data.error || (data.errors && Object.values(data.errors).join(', ')) || 'Registration failed');
      }
    } catch (err) {
      setError('Network/server error');
    }
  };
  return (
    <Paper elevation={3} sx={{padding:4, maxWidth:400, margin:'120px auto'}}>
      <Typography variant="h5" gutterBottom>Register</Typography>
      <Box component="form" noValidate autoComplete="off" onSubmit={handleSubmit}>
        <TextField label="Username" name="username" variant="outlined" fullWidth margin="normal" value={form.username} onChange={handleChange} />
        <TextField label="Email" name="email" type="email" variant="outlined" fullWidth margin="normal" value={form.email} onChange={handleChange} />
        <TextField label="Password" name="password" type="password" variant="outlined" fullWidth margin="normal" value={form.password} onChange={handleChange} />
        <TextField label="Company Name" name="company_name" variant="outlined" fullWidth margin="normal" value={form.company_name} onChange={handleChange} required />
        <TextField label="Master Password" name="master_password" type="password" variant="outlined" fullWidth margin="normal" value={form.master_password} onChange={handleChange} required />
        {error && <Typography color="error" mt={2}>{error}</Typography>}
        {success && <Typography color="success.main" mt={2}>{success}</Typography>}
        <Button variant="contained" color="primary" fullWidth sx={{mt:2}} type="submit">Register</Button>
      </Box>
    </Paper>
  );
}
