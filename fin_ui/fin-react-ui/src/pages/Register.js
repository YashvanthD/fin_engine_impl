import React from 'react';
import { TextField, Button, Paper, Typography, Box } from '@mui/material';

export default function Register() {
  return (
    <Paper elevation={3} sx={{padding:4, maxWidth:400, margin:'40px auto'}}>
      <Typography variant="h5" gutterBottom>Register</Typography>
      <Box component="form" noValidate autoComplete="off">
        <TextField label="Username" variant="outlined" fullWidth margin="normal" />
        <TextField label="Email" type="email" variant="outlined" fullWidth margin="normal" />
        <TextField label="Password" type="password" variant="outlined" fullWidth margin="normal" />
        <Button variant="contained" color="primary" fullWidth sx={{mt:2}}>Register</Button>
      </Box>
    </Paper>
  );
}
