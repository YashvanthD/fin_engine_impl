import React from 'react';
import { Button, Paper, Typography, Stack } from '@mui/material';
import { Link } from 'react-router-dom';

export default function Landing() {
  return (
    <Paper elevation={3} sx={{padding:4, maxWidth:500, margin:'40px auto', textAlign:'center'}}>
      <Typography variant="h4" gutterBottom>Fin Engine</Typography>
      <Stack direction="row" spacing={2} justifyContent="center">
        <Button component={Link} to="/login" variant="contained">Login</Button>
        <Button component={Link} to="/register" variant="outlined">Register</Button>
        <Button component={Link} to="/home" variant="text">Home</Button>
      </Stack>
    </Paper>
  );
}
